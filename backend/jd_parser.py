"""Parse an unstructured job posting into the scorer's JD schema."""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from resume_pipeline.model_client import LLMClient

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = """Extract a structured job description from the supplied plain text.
Return ONLY one JSON object with exactly these keys:
{"role": string, "required_skills": [string], "preferred_skills": [string],
 "cgpa_min": number, "slots": integer}

Rules:
- Required skills are explicitly mandatory or central to the role.
- Preferred skills are described as preferred, nice-to-have, bonus, or optional.
- Keep compound alternatives together, such as "React.js or Next.js".
- If CGPA is absent, use 0. If slot count is absent, use 1.
- Do not invent skills that are not stated or clearly implied by the posting."""


def parse_job_description(client: LLMClient, raw_text: str) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": raw_text.strip()},
    ]
    raw = client.chat(messages, response_format_json=True, temperature=0.0)
    data = _parse_object(raw)
    return {
        "role": str(data.get("role") or "Untitled role").strip(),
        "required_skills": _string_list(data.get("required_skills")),
        "preferred_skills": _string_list(data.get("preferred_skills")),
        "cgpa_min": _bounded_float(data.get("cgpa_min"), 0.0, 10.0, 0.0),
        "slots": int(_bounded_float(data.get("slots"), 1, 1000, 1)),
    }


def _parse_object(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[A-Za-z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(cleaned)
        if not match:
            raise ValueError("model did not return a JSON object")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")
    return data


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _bounded_float(value: Any, minimum: float, maximum: float, fallback: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return min(max(numeric, minimum), maximum)
