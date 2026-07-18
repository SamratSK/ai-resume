"""Shared strict-JSON parsing helpers: strip markdown code fences, then
parse — with a fallback that extracts the outermost {..}/[..] block if the
model added stray commentary despite instructions not to.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

_FENCE_OPEN_RE = re.compile(r"^```[a-zA-Z]*\n?")
_FENCE_CLOSE_RE = re.compile(r"\n?```$")


def strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE_OPEN_RE.sub("", text)
        text = _FENCE_CLOSE_RE.sub("", text)
    return text.strip()


def parse_json_object(raw: str) -> Dict[str, Any]:
    cleaned = strip_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(cleaned[start : end + 1])
        else:
            raise
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def parse_json_array(raw: str) -> List[Any]:
    cleaned = strip_fences(raw)
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
