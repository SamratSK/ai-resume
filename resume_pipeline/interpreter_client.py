"""Value interpretation against the small local model.

The model only identifies the source scale. Deterministic Python code in
``merge.normalize_grade`` performs the actual conversion.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from resume_pipeline.model_client import LLMClient

_FENCE_OPEN_RE = re.compile(r"^```[a-zA-Z]*\n?")
_FENCE_CLOSE_RE = re.compile(r"\n?```$")

SYSTEM_PROMPT = """You interpret how a raw numeric/verbal value was written on a resume. \
You do NOT convert between scales and you do NOT do arithmetic — you only read what is \
already there and say what scale it appears to be on.

Valid "scale" values: "cgpa_10" (out of 10), "percentage", "gpa_4" (out of 4), "unknown".

Examples:
- "eight point four" -> value: 8.4, scale: "cgpa_10", confident: true
- "seventy-nine percent" -> value: 79, scale: "percentage", confident: true
- "3.6/4" -> value: 3.6, scale: "gpa_4", confident: true
- a bare number with no unit, e.g. "8.4" -> value: 8.4, scale: "unknown", confident: false

You will receive a JSON array of items, each with doc_id, field, raw_value. \
Return ONLY a JSON array of the same length, same order, each item exactly:
{"doc_id": str, "field": str, "value": number|string, "scale": "cgpa_10"|"percentage"|"gpa_4"|"unknown", "confident": bool}

No markdown fences, no commentary, no extra keys."""

_RETRY_INSTRUCTION = (
    "That response was not a valid JSON array matching the requested shape. "
    "Reply again with ONLY the JSON array — no markdown fences, no commentary."
)


@dataclass
class InterpretItem:
    doc_id: str
    field: str
    raw_value: str


@dataclass
class InterpretResult:
    doc_id: str
    field: str
    value: Any
    scale: str
    confident: bool


def interpret_values(client: LLMClient, items: List[InterpretItem]) -> List[InterpretResult]:
    """Chunks items into batches of at most client.endpoint.batch_size and
    interprets each chunk independently — one bad chunk never drops the rest."""
    batch_size = max(client.endpoint.batch_size, 1)
    results: List[InterpretResult] = []
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        results.extend(_interpret_chunk(client, chunk))
    return results


def _interpret_chunk(client: LLMClient, chunk: List[InterpretItem]) -> List[InterpretResult]:
    if not chunk:
        return []

    request_payload = [
        {"doc_id": item.doc_id, "field": item.field, "raw_value": item.raw_value} for item in chunk
    ]
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(request_payload)},
    ]

    total_attempts = 1 + max(client.endpoint.max_retries, 0)
    parsed: Optional[List[Dict[str, Any]]] = None

    for attempt in range(total_attempts):
        try:
            raw = client.chat(messages, response_format_json=False)
        except httpx.HTTPError:
            continue
        try:
            candidate = _parse_json_array(raw)
        except (json.JSONDecodeError, ValueError):
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": _RETRY_INSTRUCTION},
            ]
            continue
        parsed = candidate
        break

    if parsed is None:
        # Interpreter unreachable/broken for this chunk: fall back to
        # unconverted, low-confidence passthrough rather than dropping items.
        return [
            InterpretResult(doc_id=item.doc_id, field=item.field, value=item.raw_value, scale="unknown", confident=False)
            for item in chunk
        ]

    by_key = {(str(entry.get("doc_id")), str(entry.get("field"))): entry for entry in parsed if isinstance(entry, dict)}

    results: List[InterpretResult] = []
    for item in chunk:
        entry = by_key.get((item.doc_id, item.field))
        if entry is None:
            results.append(InterpretResult(item.doc_id, item.field, item.raw_value, "unknown", False))
            continue
        scale = entry.get("scale") if entry.get("scale") in ("cgpa_10", "percentage", "gpa_4", "unknown") else "unknown"
        results.append(
            InterpretResult(
                doc_id=item.doc_id,
                field=item.field,
                value=entry.get("value", item.raw_value),
                scale=scale,
                confident=bool(entry.get("confident", False)),
            )
        )
    return results


def _parse_json_array(raw: str) -> List[Dict[str, Any]]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = _FENCE_OPEN_RE.sub("", cleaned)
        cleaned = _FENCE_CLOSE_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            data = json.loads(cleaned[start : end + 1])
        else:
            raise
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")
    return data
