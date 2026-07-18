"""Generates the 3 reasoning bullets that EXPLAIN a candidate's score. They
never change it — this module only ever runs after every score component
(including the holistic adjustment) is already final. Batched across
candidates like every other LLM call in Stage 2.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import httpx

from resume_pipeline.model_client import LLMClient
from scoring.batch_resolve import Item, resolve_batched
from scoring.cache import DiskCache
from scoring.json_utils import parse_json_array

SYSTEM_PROMPT = """Given MULTIPLE candidates' computed scoring breakdowns for a job role, \
write exactly 3 short reasoning bullets per candidate that EXPLAIN the score — they never \
change it. Mix positive and negative points as warranted, drawing only from that candidate's \
own breakdown: matched/missing skills, CGPA status, project/experience assessment, the \
holistic adjustment reason, and any parse-quality caveats. Each bullet is one short sentence. \
Never mix material between candidates.

You will receive a JSON object with the JD role and a "candidates" array, each with doc_id \
and breakdown.

Return ONLY a JSON array covering EVERY candidate, each entry exactly:
{"doc_id": str, "bullets": ["...", "...", "..."]}"""

_RETRY_INSTRUCTION = (
    "That response was not valid JSON matching the requested shape. "
    "Reply again with ONLY the JSON array — no markdown fences, no commentary."
)


def generate_reasoning_bullets_batch(
    jd_role: str, candidates: List[Tuple[str, Dict[str, Any]]], llm_client: LLMClient, cache: DiskCache, batch_size: int
) -> Dict[str, List[str]]:
    """candidates: (doc_id, breakdown_summary). Returns {doc_id: [bullet, bullet, bullet]}."""
    items: List[Item] = [(doc_id, breakdown_summary, ["reasoning_bullets", jd_role, breakdown_summary]) for doc_id, breakdown_summary in candidates]

    def _resolve_chunk(chunk: List[Item]) -> Dict[str, dict]:
        return _resolve_bullets_batch(jd_role, chunk, llm_client)

    resolved = resolve_batched("reasoning_bullets", items, cache, batch_size, _resolve_chunk)

    output: Dict[str, List[str]] = {}
    breakdown_by_doc = dict(candidates)
    for doc_id, cached in resolved.items():
        bullets = cached.get("bullets") or []
        if len(bullets) != 3:
            bullets = _fallback_bullets(breakdown_by_doc[doc_id])
        output[doc_id] = bullets
    return output


def _resolve_bullets_batch(jd_role: str, chunk: List[Item], llm_client: LLMClient) -> Dict[str, dict]:
    request_payload = [{"doc_id": doc_id, "breakdown": breakdown_summary} for doc_id, breakdown_summary, _ in chunk]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps({"role": jd_role, "candidates": request_payload})},
    ]

    total_attempts = 1 + max(llm_client.endpoint.max_retries, 0)
    parsed: Any = None

    for _ in range(total_attempts):
        try:
            raw = llm_client.chat(messages, response_format_json=False)
        except httpx.HTTPError:
            continue
        try:
            parsed = parse_json_array(raw)
        except (json.JSONDecodeError, ValueError):
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
    for doc_id, breakdown_summary, _key_parts in chunk:
        entry = by_doc.get(doc_id)
        bullets = entry.get("bullets") if entry else None
        if isinstance(bullets, list) and len(bullets) == 3 and all(isinstance(b, str) for b in bullets):
            results[doc_id] = {"bullets": bullets}
        else:
            results[doc_id] = {"bullets": _fallback_bullets(breakdown_summary)}
    return results


def _fallback_bullets(breakdown_summary: Dict[str, Any]) -> List[str]:
    required = breakdown_summary.get("required_skills", {})
    preferred = breakdown_summary.get("preferred_skills", {})
    cgpa = breakdown_summary.get("cgpa", {})
    return [
        f"Required skills: {required.get('detail', 'not available')}",
        f"Preferred skills: {preferred.get('detail', 'not available')}",
        f"CGPA: {cgpa.get('detail', 'not available')}",
    ]
