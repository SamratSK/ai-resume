"""Tiered skill matching: exact/synonym resolved in pure Python; only the
leftover JD skills (nothing Python could resolve) go to the LLM, which
picks a tier only — Python always assigns the point credit for that tier.

JD skills may express alternatives ("React.js or Next.js", "Git/GitHub")
using " or " / "/" — matching any one alternative satisfies the requirement.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import httpx
from pydantic import BaseModel

from resume_pipeline.model_client import LLMClient
from resume_pipeline.schema import ResumeRecord
from scoring.batch_resolve import Item, resolve_batched
from scoring.cache import DiskCache
from scoring.config import TierCredits
from scoring.jd_loader import JobDescription
from scoring.json_utils import parse_json_array

_SYNONYMS_PATH = Path(__file__).resolve().parent / "data" / "synonyms.json"
_ALT_SPLIT_RE = re.compile(r"\s+or\s+|/")
_WHITESPACE_RE = re.compile(r"\s+")
_STRIP_CHARS_RE = re.compile(r"[.\-]")

_VALID_TIERS = ("exact", "synonym", "partial", "implicit", "missing")

SYSTEM_PROMPT = """You classify how well MULTIPLE candidates' resumes cover specific \
job-required skills that pure string matching could NOT resolve — you only see the leftover \
skills that need judgment, for each candidate.

Tiers (choose exactly one per skill per candidate):
- "partial": the candidate has a clearly related but narrower/broader skill (e.g. JD wants \
PostgreSQL, candidate lists "SQL" or "databases").
- "implicit": the skill is not named directly, but is strongly implied by a project or \
experience description (e.g. a project description that clearly used REST APIs without \
saying "REST").
- "missing": no reasonable evidence the candidate has this skill.

You will receive a JSON object with the JD role and a "candidates" array. Each candidate has \
a doc_id, their skills list, project one-liners, and experience entries (each with evidence \
text), plus the list of JD skills to classify for that candidate specifically.

Return ONLY a JSON array covering EVERY candidate and EVERY one of their listed skills — do \
not skip any — each entry exactly:
[{"doc_id": str, "jd_skill": str, "tier": "partial"|"implicit"|"missing", "matched_against": str|null, "evidence": str|null}]

matched_against is the specific candidate skill/project/experience text that supports the \
tier (null if missing). evidence is a short verbatim quote from that candidate's text (null \
if missing). Never invent evidence, and never mix up evidence between candidates."""

_RETRY_INSTRUCTION = (
    "That response was not a valid JSON array matching the requested shape. "
    "Reply again with ONLY the JSON array — no markdown fences, no commentary."
)


class SkillMatch(BaseModel):
    jd_skill: str
    tier: str  # exact | synonym | partial | implicit | missing
    matched_against: Optional[str] = None
    evidence: Optional[str] = None
    credit: float
    flagged: bool
    note: Optional[str] = None  # set when an LLM classification failed and defaulted


def normalize(text: str) -> str:
    text = _STRIP_CHARS_RE.sub("", text.lower())
    return _WHITESPACE_RE.sub(" ", text).strip()


def split_alternatives(skill: str) -> List[str]:
    parts = _ALT_SPLIT_RE.split(skill)
    return [p.strip() for p in parts if p.strip()]


def _load_synonym_lookup() -> Dict[str, Set[str]]:
    """normalized member -> normalized members of its whole group (self included)."""
    with open(_SYNONYMS_PATH, "r", encoding="utf-8") as fh:
        groups = json.load(fh)
    lookup: Dict[str, Set[str]] = {}
    for group in groups:
        normalized_members = {normalize(m) for m in group}
        for member in normalized_members:
            lookup[member] = normalized_members
    return lookup


_SYNONYM_LOOKUP = _load_synonym_lookup()


def _word_in_text(word: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _credit_and_flag(tier: str, tier_credits: TierCredits) -> Tuple[float, bool]:
    credit = tier_credits.get(tier) if tier in _VALID_TIERS else tier_credits.missing
    flagged = tier in ("partial", "implicit")
    return credit, flagged


def _try_python_match(
    alternatives: List[str], candidate_skills: List[Tuple[str, Optional[str]]], tier_credits: TierCredits
) -> Optional[SkillMatch]:
    alt_norms = [normalize(a) for a in alternatives]

    for raw, evidence in candidate_skills:
        if normalize(raw) in alt_norms:
            credit, flagged = _credit_and_flag("exact", tier_credits)
            return SkillMatch(jd_skill="", tier="exact", matched_against=raw, evidence=evidence, credit=credit, flagged=flagged)

    for raw, evidence in candidate_skills:
        group = _SYNONYM_LOOKUP.get(normalize(raw))
        if not group:
            continue
        for alt_norm in alt_norms:
            if any(_word_in_text(member, alt_norm) for member in group):
                credit, flagged = _credit_and_flag("synonym", tier_credits)
                return SkillMatch(jd_skill="", tier="synonym", matched_against=raw, evidence=evidence, credit=credit, flagged=flagged)

    return None


def _python_match_list(
    jd_skills: List[str], record: ResumeRecord, tier_credits: TierCredits
) -> Tuple[List[SkillMatch], List[int]]:
    candidate_skills = [(s.raw_value, s.evidence) for s in record.skills if s.raw_value]
    matches: List[SkillMatch] = []
    leftover_indices: List[int] = []

    for idx, jd_skill in enumerate(jd_skills):
        alternatives = split_alternatives(jd_skill)
        match = _try_python_match(alternatives, candidate_skills, tier_credits)
        if match is None:
            credit, flagged = _credit_and_flag("missing", tier_credits)
            matches.append(SkillMatch(jd_skill=jd_skill, tier="missing", credit=credit, flagged=flagged))
            leftover_indices.append(idx)
        else:
            match.jd_skill = jd_skill
            matches.append(match)

    return matches, leftover_indices


def match_skills(
    jd: JobDescription, record: ResumeRecord, llm_client: LLMClient, cache: DiskCache, tier_credits: TierCredits, batch_size: int = 1
) -> Tuple[List[SkillMatch], List[SkillMatch]]:
    """Single-candidate convenience wrapper around resolve_skill_matches_for_candidates
    (a batch of one) — useful for scoring one resume on demand without the full pipeline."""
    result = resolve_skill_matches_for_candidates(jd, [("_single", record)], llm_client, cache, tier_credits, batch_size)
    return result["_single"]


def resolve_skill_matches_for_candidates(
    jd: JobDescription,
    candidates: List[Tuple[str, ResumeRecord]],
    llm_client: LLMClient,
    cache: DiskCache,
    tier_credits: TierCredits,
    batch_size: int,
) -> Dict[str, Tuple[List[SkillMatch], List[SkillMatch]]]:
    """Returns {doc_id: (required_matches, preferred_matches)}. Python
    exact/synonym matching runs per-candidate (cheap, no LLM); only the
    leftover skills per candidate go through cache-then-batch LLM
    resolution — one call can cover up to batch_size candidates at once,
    but each candidate's result is still cached under its own key."""
    per_candidate: Dict[str, list] = {}
    items: List[Item] = []

    for doc_id, record in candidates:
        required_matches, required_leftover = _python_match_list(jd.required_skills, record, tier_credits)
        preferred_matches, preferred_leftover = _python_match_list(jd.preferred_skills, record, tier_credits)
        per_candidate[doc_id] = [required_matches, preferred_matches, required_leftover, preferred_leftover]

        leftover_skills = [required_matches[i].jd_skill for i in required_leftover] + [
            preferred_matches[i].jd_skill for i in preferred_leftover
        ]
        if leftover_skills:
            candidate_payload = _build_candidate_payload(record)
            key_parts = ["skill_tier_classification", jd.role, leftover_skills, candidate_payload]
            items.append((doc_id, (leftover_skills, candidate_payload), key_parts))

    def _resolve_chunk(chunk: List[Item]) -> Dict[str, dict]:
        return _resolve_leftovers_via_llm_batch(jd, chunk, llm_client)

    resolved = resolve_batched("skill_tier", items, cache, batch_size, _resolve_chunk)

    output: Dict[str, Tuple[List[SkillMatch], List[SkillMatch]]] = {}
    for doc_id, (required_matches, preferred_matches, required_leftover, preferred_leftover) in per_candidate.items():
        classifications = resolved.get(doc_id, {}).get("classifications", [])
        by_skill = {c["jd_skill"]: c for c in classifications}
        for i in required_leftover:
            _apply_classification(required_matches, i, by_skill, tier_credits)
        for i in preferred_leftover:
            _apply_classification(preferred_matches, i, by_skill, tier_credits)
        output[doc_id] = (required_matches, preferred_matches)

    return output


def _build_candidate_payload(record: ResumeRecord) -> dict:
    return {
        "skills": [s.raw_value for s in record.skills if s.raw_value],
        "projects": [{"title": p.title, "one_liner": p.one_liner, "evidence": p.evidence} for p in record.projects],
        "experience": [
            {"company": e.company, "role": e.role, "duration": e.duration, "evidence": e.evidence}
            for e in record.experience
        ],
    }


def _apply_classification(matches: List[SkillMatch], idx: int, by_skill: Dict[str, dict], tier_credits: TierCredits) -> None:
    skill = matches[idx].jd_skill
    entry = by_skill.get(skill)
    if entry is None:
        return
    credit, flagged = _credit_and_flag(entry["tier"], tier_credits)
    matches[idx] = SkillMatch(
        jd_skill=skill,
        tier=entry["tier"],
        matched_against=entry.get("matched_against"),
        evidence=entry.get("evidence"),
        credit=credit,
        flagged=flagged,
        note=entry.get("note"),
    )


def _resolve_leftovers_via_llm_batch(jd: JobDescription, chunk: List[Item], llm_client: LLMClient) -> Dict[str, dict]:
    request_payload = [
        {"doc_id": doc_id, "jd_skills": leftover_skills, "candidate": candidate_payload}
        for doc_id, (leftover_skills, candidate_payload), _ in chunk
    ]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps({"role": jd.role, "candidates": request_payload})},
    ]

    total_attempts = 1 + max(llm_client.endpoint.max_retries, 0)
    parsed: Optional[List[dict]] = None
    last_error: Optional[str] = None

    for _ in range(total_attempts):
        try:
            raw = llm_client.chat(messages, response_format_json=False)
        except httpx.HTTPError as exc:
            last_error = f"model request failed: {exc}"
            continue
        try:
            parsed = parse_json_array(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = f"invalid JSON from model: {exc}"
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": _RETRY_INSTRUCTION},
            ]
            continue
        break

    by_doc_skill: Dict[Tuple[str, str], dict] = {}
    if parsed is not None:
        for entry in parsed:
            if isinstance(entry, dict) and entry.get("doc_id") and entry.get("jd_skill"):
                by_doc_skill[(str(entry["doc_id"]), str(entry["jd_skill"]))] = entry

    results: Dict[str, dict] = {}
    for doc_id, (leftover_skills, _candidate_payload), _key_parts in chunk:
        classifications = []
        for skill in leftover_skills:
            entry = by_doc_skill.get((doc_id, skill))
            tier = entry.get("tier") if entry else None
            if tier in _VALID_TIERS:
                classifications.append(
                    {
                        "jd_skill": skill,
                        "tier": tier,
                        "matched_against": entry.get("matched_against"),
                        "evidence": entry.get("evidence"),
                        "note": None,
                    }
                )
            else:
                classifications.append(
                    {
                        "jd_skill": skill,
                        "tier": "missing",
                        "matched_against": None,
                        "evidence": None,
                        "note": f"LLM batch classification unavailable/invalid, defaulted to missing ({last_error or 'no result for this candidate'})",
                    }
                )
        results[doc_id] = {"classifications": classifications}
    return results

