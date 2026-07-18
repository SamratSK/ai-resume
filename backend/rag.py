"""Persisted resume indexing and per-JD hybrid chat."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

import chromadb
import httpx

from resume_pipeline.schema import ResumeRecord

Route = Literal["structured", "semantic", "hybrid"]

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_COUNT_RE = re.compile(r"\b(how many|count|number of)\b", re.IGNORECASE)

CLASSIFIER_PROMPT = """Classify a question about a job candidate pool.
Return only JSON: {"route":"structured"|"semantic"|"hybrid"}.
structured = exact filters, comparisons, sorting, lists, or counts over resume fields/skills/scores.
semantic = qualitative judgment, summaries, project/experience relevance, or open-ended comparison.
hybrid = an exact filter followed by qualitative ranking or summarization.
/no_think"""

PLAN_PROMPT = """/no_think
Translate the candidate question into one valid JSON object. Output JSON only.
Always include exactly these four keys: filters, skills_any, sort, limit.

Example question: Who has CGPA above 8 and knows React?
Example output: {"filters":[{"field":"cgpa","op":"gt","value":8}],"skills_any":["React"],"sort":null,"limit":null}

Example question: List the top 3 candidates by score.
Example output: {"filters":[],"skills_any":[],"sort":{"field":"score","direction":"desc"},"limit":3}

Filter fields: cgpa, graduation_year, college, branch, degree, parse_quality, score.
Operators: eq, neq, gt, gte, lt, lte, contains, in.
Sort fields: cgpa, graduation_year, score, name.
Do not put lists of choices inside a field. Do not invent filters. /no_think"""

ANSWER_PROMPT = """Answer only from the supplied candidate context. Never invent candidates, values, skills,
projects, or experience. If the context is not relevant, say no relevant candidates were found.
Be concise and directly answer the question. Resume citations are appended by the application."""


@dataclass(frozen=True)
class ChatSource:
    resume_id: str
    name: str


@dataclass(frozen=True)
class ChatResult:
    answer: str
    sources: List[ChatSource]
    route_taken: Route


class OpenAICompatibleClient:
    def __init__(self, base_url: str, timeout: float = 90):
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def chat(self, messages: List[Dict[str, str]], *, json_mode: bool = False) -> str:
        payload: Dict[str, Any] = {
            "model": "local",
            "messages": messages,
            "temperature": 0,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = self._http.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def close(self) -> None:
        self._http.close()


class EmbeddingClient:
    def __init__(self, base_url: str):
        self._http = httpx.Client(base_url=base_url, timeout=90)

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        response = self._http.post("/embeddings", json={"model": "local", "input": list(texts)})
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]

    def close(self) -> None:
        self._http.close()


class ResumeIndex:
    def __init__(self, persist_dir: Path, embedding_client: EmbeddingClient):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_client = embedding_client
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            "resume_chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def index_resume(self, doc_id: str, record: ResumeRecord) -> int:
        chunks = build_chunks(doc_id, record)
        current = self.collection.get(where={"doc_id": doc_id}, include=["metadatas"])
        known = {
            item_id: metadata.get("content_hash")
            for item_id, metadata in zip(current.get("ids", []), current.get("metadatas", []) or [])
        }
        expected_ids = {chunk_id for chunk_id, _text, _meta in chunks}
        stale = [item_id for item_id in known if item_id not in expected_ids]
        if stale:
            self.collection.delete(ids=stale)

        changed = [
            (chunk_id, text, metadata)
            for chunk_id, text, metadata in chunks
            if known.get(chunk_id) != metadata["content_hash"]
        ]
        if changed:
            embeddings = self.embedding_client.embed([text for _chunk_id, text, _metadata in changed])
            self.collection.upsert(
                ids=[chunk_id for chunk_id, _text, _metadata in changed],
                documents=[text for _chunk_id, text, _metadata in changed],
                metadatas=[metadata for _chunk_id, _text, metadata in changed],
                embeddings=embeddings,
            )
        return len(changed)

    def delete_resume(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})

    def query(self, text: str, allowed_ids: Sequence[str], limit: int = 8) -> List[Dict[str, Any]]:
        if not allowed_ids:
            return []
        embedding = self.embedding_client.embed([text])[0]
        count = self.collection.count()
        if not count:
            return []
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=min(limit, count),
            where={"doc_id": {"$in": list(allowed_ids)}},
            include=["documents", "metadatas", "distances"],
        )
        rows = []
        for document, metadata, distance in zip(
            (result.get("documents") or [[]])[0],
            (result.get("metadatas") or [[]])[0],
            (result.get("distances") or [[]])[0],
        ):
            rows.append({"document": document, "metadata": metadata, "distance": distance})
        return rows


class HybridChatService:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.extracted_dir = repo_root / "extracted"
        self.output_dir = repo_root / "output"
        self.router_llm = OpenAICompatibleClient(os.getenv("RAG_ROUTER_BASE_URL", "http://127.0.0.1:8083/v1"))
        self.answer_llm = OpenAICompatibleClient(os.getenv("RAG_ANSWER_BASE_URL", "http://127.0.0.1:8080/v1"), timeout=180)
        self.embedding_client = EmbeddingClient(os.getenv("RAG_EMBED_BASE_URL", "http://127.0.0.1:8082/v1"))
        self.index = ResumeIndex(repo_root / "chroma", self.embedding_client)

    def close(self) -> None:
        self.router_llm.close()
        self.answer_llm.close()
        self.embedding_client.close()

    def index_resume(self, doc_id: str, record: ResumeRecord) -> int:
        return self.index.index_resume(doc_id, record)

    def index_all(self) -> Dict[str, int]:
        indexed: Dict[str, int] = {}
        for path in sorted(self.extracted_dir.glob("*.json")):
            try:
                record = ResumeRecord.model_validate_json(path.read_text(encoding="utf-8"))
                indexed[path.stem] = self.index.index_resume(path.stem, record)
            except Exception:
                indexed[path.stem] = -1
        return indexed

    def delete_resume(self, doc_id: str) -> None:
        self.index.delete_resume(doc_id)

    def ask(self, jd_id: str, message: str, history: List[Dict[str, str]]) -> ChatResult:
        route = self._classify(message)
        pool = self._load_pool(jd_id)
        if not pool:
            return ChatResult("No candidates are available for this job description.", [], route)

        try:
            self._ensure_index(pool)
            if route == "structured":
                plan = self._plan_with_retry(message)
                if plan is None:
                    return self._semantic(jd_id, message, history, pool, "semantic")
                filtered = execute_plan(pool, plan)
                return structured_answer(message, filtered)

            if route == "hybrid":
                plan = self._plan_with_retry(message)
                if plan is None:
                    return self._semantic(jd_id, message, history, pool, "semantic")
                filtered = execute_plan(pool, plan)
                return self._semantic(jd_id, message, history, filtered, "hybrid")

            return self._semantic(jd_id, message, history, pool, "semantic")
        except Exception as exc:
            return ChatResult(
                f"I could not complete that candidate search because a local model service failed: {exc}",
                [],
                route,
            )

    def _classify(self, message: str) -> Route:
        heuristic = heuristic_route(message)
        try:
            raw = self.router_llm.chat(
                [{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": message}],
                json_mode=True,
            )
            route = parse_json_object(raw).get("route")
            if route in {"structured", "semantic", "hybrid"}:
                # Preserve obvious exact-filter signals when the small router misses them.
                return heuristic if heuristic in {"structured", "hybrid"} else route
        except Exception:
            pass
        return heuristic

    def _plan_with_retry(self, message: str) -> Optional[Dict[str, Any]]:
        messages = [
            {"role": "system", "content": PLAN_PROMPT},
            {"role": "user", "content": message},
        ]
        for attempt in range(2):
            try:
                raw = self.answer_llm.chat(messages, json_mode=True)
                plan = parse_json_object(raw)
                return validate_plan(plan)
            except Exception:
                if attempt == 0:
                    messages.append({"role": "user", "content": "Your plan was malformed. Return only the required JSON object. /no_think"})
        return None

    def _semantic(
        self,
        jd_id: str,
        message: str,
        history: List[Dict[str, str]],
        pool: List[Dict[str, Any]],
        route: Route,
    ) -> ChatResult:
        if not pool:
            return ChatResult("No candidates matched the structured filters.", [], route)
        allowed = [candidate["doc_id"] for candidate in pool]
        rows = self.index.query(message, allowed)
        relevant = [row for row in rows if row["distance"] is None or row["distance"] <= 1.0]
        if not relevant:
            return ChatResult("No relevant candidates were found in this job's candidate pool.", [], route)

        source_ids = list(dict.fromkeys(row["metadata"]["doc_id"] for row in relevant))
        sources = [source_for(next(candidate for candidate in pool if candidate["doc_id"] == doc_id)) for doc_id in source_ids]
        jd = _load_json(self.repo_root / "jds" / f"{jd_id}.json") or {}
        shortlist = _load_json(self.output_dir / f"{jd_id}_shortlist.json") or {}
        context = "\n\n".join(
            f"[Resume {row['metadata']['doc_id']} | {row['metadata']['chunk_type']}]\n{row['document']}"
            for row in relevant
        )
        recent_history = [
            item for item in history[-8:]
            if item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str)
        ]
        messages = [
            {"role": "system", "content": ANSWER_PROMPT},
            {
                "role": "system",
                "content": f"JD: {json.dumps(jd, ensure_ascii=True)}\n"
                f"Shortlist summary: {json.dumps(_shortlist_summary(shortlist), ensure_ascii=True)}\n"
                f"Retrieved resume context:\n{context}",
            },
            *recent_history,
            {"role": "user", "content": message},
        ]
        answer = self.answer_llm.chat(messages).strip()
        if not answer:
            answer = "No relevant candidates were found in the retrieved resume context."
            sources = []
        if re.search(r"\bno relevant candidates?\b|\bno candidates? (?:were )?found\b", answer, re.IGNORECASE):
            sources = []
        return ChatResult(append_citations(answer, sources), sources, route)

    def _ensure_index(self, pool: List[Dict[str, Any]]) -> None:
        for candidate in pool:
            self.index.index_resume(candidate["doc_id"], candidate["record"])

    def _load_pool(self, jd_id: str) -> List[Dict[str, Any]]:
        score_map: Dict[str, Dict[str, Any]] = {}
        shortlist = _load_json(self.output_dir / f"{jd_id}_shortlist.json") or {}
        for section in ("shortlist", "reserve", "excluded"):
            for item in shortlist.get(section, []):
                score_map[item.get("doc_id", "")] = item

        candidates: List[Dict[str, Any]] = []
        for path in sorted(self.extracted_dir.glob("*.json")):
            try:
                record = ResumeRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            candidates.append(candidate_data(path.stem, record, score_map.get(path.stem)))
        return candidates


def build_chunks(doc_id: str, record: ResumeRecord) -> List[Tuple[str, str, Dict[str, Any]]]:
    name = field_value(record.full_name) or record.file
    skills = ", ".join(filter(None, (field_value(skill) for skill in record.skills)))
    profile = (
        f"Candidate: {name}. College: {field_value(record.college) or 'not stated'}. "
        f"Degree: {field_value(record.degree) or 'not stated'}. Branch: {field_value(record.branch) or 'not stated'}. "
        f"Graduation year: {field_value(record.graduation_year) or 'not stated'}. "
        f"CGPA: {field_value(record.cgpa) or 'not stated'}. Skills: {skills or 'not stated'}."
    )
    raw_chunks = [("profile", profile)]
    raw_chunks.extend(
        (
            f"project_{index}",
            f"Candidate: {name}. Project: {project.title or 'Untitled'}. {project.one_liner or ''}. Evidence: {project.evidence or 'not available'}.",
        )
        for index, project in enumerate(record.projects)
    )
    raw_chunks.extend(
        (
            f"experience_{index}",
            f"Candidate: {name}. Experience: {experience.role or 'Role not stated'} at {experience.company or 'company not stated'}, "
            f"{experience.duration or 'duration not stated'}. Evidence: {experience.evidence or 'not available'}.",
        )
        for index, experience in enumerate(record.experience)
    )
    return [
        (
            f"{doc_id}:{chunk_type}",
            text,
            {
                "doc_id": doc_id,
                "chunk_type": chunk_type,
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
        )
        for chunk_type, text in raw_chunks
    ]


def candidate_data(doc_id: str, record: ResumeRecord, score_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "doc_id": doc_id,
        "name": field_value(record.full_name) or record.file,
        "file": record.file,
        "college": field_value(record.college),
        "degree": field_value(record.degree),
        "branch": field_value(record.branch),
        "graduation_year": numeric_value(record.graduation_year),
        "cgpa": cgpa_value(record.cgpa),
        "parse_quality": record.parse_quality,
        "skills": [value for value in (field_value(skill) for skill in record.skills) if value],
        "score": score_data.get("score") if score_data else None,
        "record": record,
    }


def execute_plan(pool: List[Dict[str, Any]], plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = list(pool)
    for condition in plan["filters"]:
        result = [candidate for candidate in result if _matches(candidate.get(condition["field"]), condition["op"], condition["value"])]
    skills_any = [str(skill).casefold() for skill in plan["skills_any"]]
    if skills_any:
        result = [
            candidate for candidate in result
            if any(
                requested in actual.casefold() or actual.casefold() in requested
                for requested in skills_any
                for actual in candidate["skills"]
            )
        ]
    sort = plan.get("sort")
    if sort:
        reverse = sort["direction"] == "desc"
        result.sort(key=lambda candidate: _sort_value(candidate.get(sort["field"])), reverse=reverse)
    if plan.get("limit"):
        result = result[: plan["limit"]]
    return result


def structured_answer(message: str, candidates: List[Dict[str, Any]]) -> ChatResult:
    sources = [source_for(candidate) for candidate in candidates]
    if not candidates:
        return ChatResult("No candidates matched those filters.", [], "structured")
    if _COUNT_RE.search(message):
        noun = "candidate" if len(candidates) == 1 else "candidates"
        answer = f"{len(candidates)} {noun} matched: {', '.join(candidate['name'] for candidate in candidates)}."
    else:
        lines = [
            f"- {candidate['name']} ({candidate['doc_id']}): "
            f"CGPA {candidate['cgpa'] if candidate['cgpa'] is not None else 'not stated'}, "
            f"score {candidate['score'] if candidate['score'] is not None else 'not scored'}, "
            f"skills {', '.join(candidate['skills']) or 'not stated'}"
            for candidate in candidates
        ]
        answer = "Matching candidates:\n" + "\n".join(lines)
    return ChatResult(append_citations(answer, sources), sources, "structured")


def validate_plan(value: Dict[str, Any]) -> Dict[str, Any]:
    allowed_fields = {"cgpa", "graduation_year", "college", "branch", "degree", "parse_quality", "score"}
    allowed_ops = {"eq", "neq", "gt", "gte", "lt", "lte", "contains", "in"}
    filters = value.get("filters", [])
    if not isinstance(filters, list):
        raise ValueError("filters must be a list")
    clean_filters = []
    for item in filters:
        if not isinstance(item, dict) or item.get("field") not in allowed_fields or item.get("op") not in allowed_ops or "value" not in item:
            raise ValueError("invalid filter")
        clean_filters.append({"field": item["field"], "op": item["op"], "value": item["value"]})
    skills = value.get("skills_any", [])
    if not isinstance(skills, list):
        raise ValueError("skills_any must be a list")
    sort = value.get("sort")
    if sort is not None:
        if not isinstance(sort, dict) or sort.get("field") not in {"cgpa", "graduation_year", "score", "name"} or sort.get("direction") not in {"asc", "desc"}:
            raise ValueError("invalid sort")
        sort = {"field": sort["field"], "direction": sort["direction"]}
    limit = value.get("limit")
    if limit is not None:
        limit = max(1, min(int(limit), 100))
    return {"filters": clean_filters, "skills_any": [str(skill) for skill in skills], "sort": sort, "limit": limit}


def parse_json_object(raw: str) -> Dict[str, Any]:
    match = _JSON_RE.search(raw)
    if not match:
        raise ValueError("No JSON object in model response")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Model response was not an object")
    return value


def heuristic_route(message: str) -> Route:
    lower = message.casefold()
    structured = bool(
        re.search(
            r"\b(above|below|over|under|at least|who has|who knows|know|knows|knowing|how many|count|cgpa|score)\b",
            lower,
        )
    )
    semantic = bool(re.search(r"\b(strongest|best|summarize|experience|project|seems|why|compare)\b", lower))
    if structured and semantic:
        return "hybrid"
    return "structured" if structured else "semantic"


def append_citations(answer: str, sources: Sequence[ChatSource]) -> str:
    if not sources:
        return answer
    citation = ", ".join(f"{source.name} ({source.resume_id})" for source in sources)
    return f"{answer.rstrip()}\n\nSources: {citation}"


def source_for(candidate: Dict[str, Any]) -> ChatSource:
    return ChatSource(resume_id=candidate["doc_id"], name=candidate["name"])


def field_value(field: Any) -> Optional[str]:
    if field is None:
        return None
    value = field.normalized_value if field.normalized_value is not None else field.raw_value
    return str(value) if value is not None else None


def numeric_value(field: Any) -> Optional[float]:
    value = field_value(field)
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group(0)) if match else None


def cgpa_value(field: Any) -> Optional[float]:
    if field is None:
        return None
    scale = (field.scale or "").casefold()
    if scale and scale not in {"cgpa_10", "cgpa", "10"}:
        return None
    return numeric_value(field)


def _matches(actual: Any, op: str, expected: Any) -> bool:
    if actual is None:
        return op == "neq" and expected is not None
    if op in {"gt", "gte", "lt", "lte"}:
        try:
            left, right = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {"gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right}[op]
    if op == "contains":
        return str(expected).casefold() in str(actual).casefold()
    if op == "in":
        values = expected if isinstance(expected, list) else [expected]
        return any(str(actual).casefold() == str(value).casefold() for value in values)
    equal = str(actual).casefold() == str(expected).casefold()
    return equal if op == "eq" else not equal


def _sort_value(value: Any) -> Tuple[bool, Any]:
    return value is not None, value if value is not None else 0


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _shortlist_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        section: [
            {"doc_id": item.get("doc_id"), "rank": item.get("rank"), "score": item.get("score")}
            for item in payload.get(section, [])
        ]
        for section in ("shortlist", "reserve", "excluded")
    }
