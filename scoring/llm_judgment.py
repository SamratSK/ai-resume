"""LLM-assessed (judgment) scoring components: projects/experience quality
against a fixed rubric, and the holistic ±N adjustment. Both are bounded,
clamped in Python, and cached per-candidate — but resolved in batches of
up to batch_size cache-miss candidates per LLM call, via batch_resolve.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import httpx

from resume_pipeline.model_client import LLMClient
from resume_pipeline.schema import ResumeRecord
from scoring.batch_resolve import Item, resolve_batched
from scoring.cache import DiskCache
from scoring.config import ProjectsRubric
from scoring.jd_loader import JobDescription
from scoring.json_utils import parse_json_array
from scoring.score_components import ComponentResult

_RETRY_INSTRUCTION = (
    "That response was not valid JSON matching the requested shape. "
    "Reply again with ONLY the JSON — no markdown fences, no commentary."
)


# ---------------------------------------------------------------------------
# Projects & experience quality (0..rubric.total_max)
# ---------------------------------------------------------------------------


def assess_projects_experience_batch(
    jd: JobDescription,
    candidates: List[Tuple[str, ResumeRecord]],
    llm_client: LLMClient,
    cache: DiskCache,
    rubric: ProjectsRubric,
    max_points: float,
    batch_size: int,
) -> Dict[str, ComponentResult]:
    items: List[Item] = []
    zero_results: Dict[str, ComponentResult] = {}

    for doc_id, record in candidates:
        projects_payload = [{"title": p.title, "one_liner": p.one_liner, "evidence": p.evidence} for p in record.projects]
        experience_payload = [
            {"company": e.company, "role": e.role, "duration": e.duration, "evidence": e.evidence}
            for e in record.experience
        ]
        if not projects_payload and not experience_payload:
            zero_results[doc_id] = ComponentResult(
                points=0.0,
                max_points=max_points,
                source="python",
                detail="No projects or experience were extracted -> 0 points (no LLM call needed).",
            )
            continue
        key_parts = [
            "projects_experience_score",
            jd.role,
            projects_payload,
            experience_payload,
            rubric.relevance_max,
            rubric.depth_max,
            rubric.breadth_max,
            rubric.total_max,
        ]
        items.append((doc_id, (projects_payload, experience_payload), key_parts))

    def _resolve_chunk(chunk: List[Item]) -> Dict[str, dict]:
        return _resolve_projects_score_batch(jd.role, chunk, llm_client, rubric)

    resolved = resolve_batched("projects_experience", items, cache, batch_size, _resolve_chunk)

    output = dict(zero_results)
    for doc_id, cached in resolved.items():
        points = max(0, min(cached["score"], rubric.total_max))
        if rubric.total_max != max_points:  # defensive: config should keep these equal
            points = round(points * (max_points / rubric.total_max), 2)
        detail = cached["justification"]
        if cached.get("fallback_used"):
            detail = f"[fallback heuristic used] {detail}"
        meta = {"justification": cached["justification"], "signals": cached.get("signals", []), "fallback_used": cached.get("fallback_used", False)}
        output[doc_id] = ComponentResult(points=points, max_points=max_points, source="llm", detail=detail, meta=meta)

    return output


def _build_rubric_prompt(rubric: ProjectsRubric) -> str:
    return f"""You assess MULTIPLE candidates' projects and experience against a job role, \
using this fixed rubric. Be consistent — you are called at temperature 0.

- Relevance of projects to the role: 0-{rubric.relevance_max} points
- Depth/deployment signals (deployed apps, real users, internships at real companies): 0-{rubric.depth_max} points
- Breadth/initiative: 0-{rubric.breadth_max} points

Total per candidate must be an integer between 0 and {rubric.total_max}. Base each candidate's \
assessment ONLY on that candidate's own projects and experience — never assume anything not \
stated, and never let one candidate's material influence another's score.

You will receive a JSON object with the JD role and a "candidates" array, each with doc_id, \
projects, and experience.

Return ONLY a JSON array covering EVERY candidate, each entry exactly:
{{"doc_id": str, "score": integer 0-{rubric.total_max}, "justification": "one sentence", "signals": ["short phrase", ...]}}"""


def _resolve_projects_score_batch(role: str, chunk: List[Item], llm_client: LLMClient, rubric: ProjectsRubric) -> Dict[str, dict]:
    request_payload = [
        {"doc_id": doc_id, "projects": projects_payload, "experience": experience_payload}
        for doc_id, (projects_payload, experience_payload), _ in chunk
    ]
    messages = [
        {"role": "system", "content": _build_rubric_prompt(rubric)},
        {"role": "user", "content": json.dumps({"role": role, "candidates": request_payload})},
    ]

    total_attempts = 1 + max(llm_client.endpoint.max_retries, 0)
    parsed: Any = None
    last_error = None

    for _ in range(total_attempts):
        try:
            raw = llm_client.chat(messages, response_format_json=False)
        except httpx.HTTPError as exc:
            last_error = f"model request failed: {exc}"
            continue
        try:
            parsed = parse_json_array(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = f"invalid JSON: {exc}"
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": _RETRY_INSTRUCTION},
            ]
            continue
        break

    by_doc: Dict[str, dict] = {}
    if parsed is not None:
        for entry in parsed:
            if isinstance(entry, dict) and entry.get("doc_id"):
                by_doc[str(entry["doc_id"])] = entry

    results: Dict[str, dict] = {}
    for doc_id, (projects_payload, experience_payload), _ in chunk:
        validated = _validate_project_entry(by_doc.get(doc_id), rubric)
        if validated is not None:
            results[doc_id] = validated
        else:
            results[doc_id] = _fallback_heuristic(
                projects_payload, experience_payload, rubric, last_error or f"no valid entry for {doc_id} in batch response"
            )
    return results


def _validate_project_entry(entry: Any, rubric: ProjectsRubric) -> Dict[str, Any] | None:
    if not isinstance(entry, dict) or "score" not in entry:
        return None
    try:
        score = int(round(float(entry["score"])))
    except (TypeError, ValueError):
        return None
    score = max(0, min(score, rubric.total_max))
    justification = str(entry.get("justification") or "").strip() or "No justification provided by model."
    signals = entry.get("signals") if isinstance(entry.get("signals"), list) else []
    return {"score": score, "justification": justification, "signals": [str(s) for s in signals], "fallback_used": False}


def _fallback_heuristic(
    projects_payload: List[dict], experience_payload: List[dict], rubric: ProjectsRubric, last_error: Any
) -> Dict[str, Any]:
    project_count = len(projects_payload)
    has_experience = len(experience_payload) > 0
    if project_count >= 3 or has_experience:
        score = rubric.total_max
    else:
        score = round(rubric.total_max * (project_count / 3))
    return {
        "score": score,
        "justification": (
            f"LLM assessment failed after retry ({last_error or 'unknown error'}); "
            "used fallback heuristic (3+ projects or any internship = full score, else scaled by project count)."
        ),
        "signals": ["fallback_heuristic"],
        "fallback_used": True,
    }


# ---------------------------------------------------------------------------
# Holistic adjustment (-max_abs..+max_abs)
# ---------------------------------------------------------------------------


def holistic_adjustment_batch(
    jd: JobDescription,
    candidates: List[Tuple[str, ResumeRecord, Dict[str, Any]]],
    llm_client: LLMClient,
    cache: DiskCache,
    max_abs: float,
    batch_size: int,
) -> Dict[str, ComponentResult]:
    """candidates: (doc_id, record, breakdown_summary_so_far)."""
    items: List[Item] = []
    for doc_id, record, breakdown_summary in candidates:
        resume_summary = _build_resume_summary(record)
        key_parts = ["holistic_adjustment", jd.role, breakdown_summary, resume_summary, max_abs]
        items.append((doc_id, (breakdown_summary, resume_summary), key_parts))

    def _resolve_chunk(chunk: List[Item]) -> Dict[str, dict]:
        return _resolve_adjustment_batch(jd.role, chunk, llm_client, max_abs)

    resolved = resolve_batched("holistic_adjustment", items, cache, batch_size, _resolve_chunk)

    output: Dict[str, ComponentResult] = {}
    for doc_id, cached in resolved.items():
        adjustment = max(-max_abs, min(cached["adjustment"], max_abs))
        meta = {"reason": cached["reason"], "fallback_used": cached.get("fallback_used", False)}
        output[doc_id] = ComponentResult(points=adjustment, max_points=max_abs, source="llm", detail=cached["reason"], meta=meta)
    return output


def _build_resume_summary(record: ResumeRecord) -> Dict[str, Any]:
    return {
        "degree": record.degree.raw_value if record.degree else None,
        "branch": record.branch.raw_value if record.branch else None,
        "college": record.college.raw_value if record.college else None,
        "cgpa_raw": record.cgpa.raw_value if record.cgpa else None,
        "cgpa_normalized": record.cgpa.normalized_value if record.cgpa else None,
        "cgpa_scale": record.cgpa.scale if record.cgpa else None,
        "skills_count": len(record.skills),
        "projects_count": len(record.projects),
        "experience_count": len(record.experience),
        "certifications_count": len(record.certifications),
        "parse_quality": record.parse_quality,
    }


def _adjustment_system_prompt(max_abs: float) -> str:
    bound = int(max_abs) if float(max_abs).is_integer() else max_abs
    return f"""You review MULTIPLE candidates' full computed score breakdowns for a job role \
and may nudge each candidate's total score by an integer between -{bound} and +{bound} to \
correct for signal conflicts the mechanical scoring can't see on its own — e.g. a very high \
CGPA paired with zero projects, a perfect skill-tier match paired with an unrelated academic \
branch, or strong practical signals despite a weaker skill-tier match. Be conservative: most \
candidates should get an adjustment of 0. Judge each candidate ONLY on their own breakdown and \
summary — never let one candidate's material influence another's adjustment.

You will receive a JSON object with the JD role and a "candidates" array, each with doc_id, \
breakdown, and resume_summary.

Return ONLY a JSON array covering EVERY candidate, each entry exactly:
{{"doc_id": str, "adjustment": integer -{bound} to {bound}, "reason": "one sentence"}}"""


def _resolve_adjustment_batch(role: str, chunk: List[Item], llm_client: LLMClient, max_abs: float) -> Dict[str, dict]:
    request_payload = [
        {"doc_id": doc_id, "breakdown": breakdown_summary, "resume_summary": resume_summary}
        for doc_id, (breakdown_summary, resume_summary), _ in chunk
    ]
    messages = [
        {"role": "system", "content": _adjustment_system_prompt(max_abs)},
        {"role": "user", "content": json.dumps({"role": role, "candidates": request_payload})},
    ]

    total_attempts = 1 + max(llm_client.endpoint.max_retries, 0)
    parsed: Any = None
    last_error = None

    for _ in range(total_attempts):
        try:
            raw = llm_client.chat(messages, response_format_json=False)
        except httpx.HTTPError as exc:
            last_error = f"model request failed: {exc}"
            continue
        try:
            parsed = parse_json_array(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = f"invalid JSON: {exc}"
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": _RETRY_INSTRUCTION},
            ]
            continue
        break

    by_doc: Dict[str, dict] = {}
    if parsed is not None:
        for entry in parsed:
            if isinstance(entry, dict) and entry.get("doc_id"):
                by_doc[str(entry["doc_id"])] = entry

    results: Dict[str, dict] = {}
    for doc_id, _payload, _key_parts in chunk:
        validated = _validate_adjustment_entry(by_doc.get(doc_id), max_abs)
        if validated is not None:
            results[doc_id] = validated
        else:
            results[doc_id] = {
                "adjustment": 0,
                "reason": f"Holistic adjustment skipped due to model failure ({last_error or f'no valid entry for {doc_id}'}).",
                "fallback_used": True,
            }
    return results


def _validate_adjustment_entry(entry: Any, max_abs: float) -> Dict[str, Any] | None:
    if not isinstance(entry, dict) or "adjustment" not in entry:
        return None
    try:
        adjustment = int(round(float(entry["adjustment"])))
    except (TypeError, ValueError):
        return None
    adjustment = max(-max_abs, min(adjustment, max_abs))
    reason = str(entry.get("reason") or "").strip() or "No reason provided by model."
    return {"adjustment": adjustment, "reason": reason, "fallback_used": False}
