"""Field extraction against the 8090-role model (Gemma via the gateway).

Sends the full resume text, gets back strict JSON. Never asks the model to
do arithmetic or scale conversion — that belongs to interpreter_client.py.
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

SYSTEM_PROMPT = """You are a strict information-extraction engine for resumes. \
You output ONLY a single JSON object — no markdown fences, no commentary, no explanations.

Rules:
- Never invent, guess, or infer a value that is not literally present in the text.
- raw_value must be copied verbatim (same characters) from the resume text.
- evidence must be a short verbatim quote (under 200 characters) of the text \
surrounding raw_value that supports it. Do not paraphrase the evidence.
- confidence is "high" if the field is stated unambiguously, "medium" if it \
required minor inference (e.g. picking the most recent degree among several), \
"low" if it's a weak guess.
- If a field is not present anywhere in the text, its value MUST be JSON null \
(not an object with null members).
- Extract skills from the ENTIRE document, not only text under a "Skills" heading \
— pull technologies/tools mentioned in projects, experience, coursework, etc. too.
- Do NOT extract age, date of birth, gender, sex, marital status, religion, caste, \
nationality, disability status, or photo/appearance descriptions, under any field \
name, including additional_fields. If you notice such information, skip it silently.
- additional_fields is for anything clearly resume-relevant but outside the fixed \
schema (e.g. "LinkedIn URL", "10th percentage", "languages known", "hackathon awards").

Return exactly this JSON shape:
{
  "full_name": {"raw_value": str, "confidence": "high"|"medium"|"low", "evidence": str} | null,
  "email": {"raw_value": str, "confidence": ..., "evidence": str} | null,
  "phone": {"raw_value": str, "confidence": ..., "evidence": str} | null,
  "college": {"raw_value": str, "confidence": ..., "evidence": str} | null,
  "degree": {"raw_value": str, "confidence": ..., "evidence": str} | null,
  "branch": {"raw_value": str, "confidence": ..., "evidence": str} | null,
  "graduation_year": {"raw_value": str, "confidence": ..., "evidence": str} | null,
  "cgpa": {"raw_value": str, "confidence": ..., "evidence": str} | null,
  "skills": [{"raw_value": str, "confidence": ..., "evidence": str}, ...],
  "projects": [{"title": str, "one_liner": str, "confidence": ..., "evidence": str}, ...],
  "experience": [{"company": str, "role": str, "duration": str, "confidence": ..., "evidence": str}, ...],
  "certifications": [{"raw_value": str, "confidence": ..., "evidence": str}, ...],
  "additional_fields": [{"field_name": str, "raw_value": str, "data_type": str, "confidence": ..., "evidence": str}, ...]
}"""

_RETRY_INSTRUCTION = (
    "That response was not valid JSON. Reply again with ONLY the JSON object "
    "described above — no markdown code fences, no leading or trailing text."
)


@dataclass
class ExtractionOutcome:
    success: bool
    data: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


def extract_fields(client: LLMClient, resume_text: str) -> ExtractionOutcome:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Resume text:\n\n{resume_text}\n\nReturn only the JSON object."},
    ]

    total_attempts = 1 + max(client.endpoint.max_retries, 0)
    last_error: Optional[str] = None

    for attempt in range(total_attempts):
        try:
            raw = client.chat(messages, response_format_json=True)
        except httpx.HTTPError as exc:
            last_error = f"model request failed: {exc}"
            continue

        try:
            parsed = _parse_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = f"invalid JSON from model: {exc}"
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": _RETRY_INSTRUCTION},
            ]
            continue

        if not isinstance(parsed, dict):
            last_error = "model JSON was not an object"
            continue

        return ExtractionOutcome(success=True, data=parsed, raw_response=raw)

    return ExtractionOutcome(success=False, error=last_error)


def _parse_json(raw: str) -> Any:
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE_OPEN_RE.sub("", text)
        text = _FENCE_CLOSE_RE.sub("", text)
    return text.strip()
