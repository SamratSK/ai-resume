"""Turns raw extraction-model JSON into a validated ResumeRecord, folds in
interpreter results by doc_id, normalizes grades, and runs sanity checks.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from resume_pipeline.interpreter_client import InterpretItem, InterpretResult
from resume_pipeline.schema import (
    PROTECTED_ATTRIBUTE_KEYWORDS,
    AdditionalField,
    ExperienceEntry,
    FieldValue,
    ProjectEntry,
    ResumeRecord,
)

_VALID_CONFIDENCE = ("high", "medium", "low")
_VALID_SCALE = ("cgpa_10", "percentage", "gpa_4", "unknown")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_YEAR_RE = re.compile(r"(19|20)\d{2}")


def build_record(file_name: str, method: str, parse_quality: str, extraction_data: Optional[Dict[str, Any]]) -> ResumeRecord:
    """Defensively builds a ResumeRecord from raw model JSON. Any single
    malformed field is dropped (set to null / excluded) rather than failing
    the whole record — one bad field must never lose the rest of a resume."""
    data = extraction_data or {}

    record = ResumeRecord(file=file_name, method=method, parse_quality=parse_quality)

    for name in ("full_name", "email", "phone", "college", "degree", "branch", "graduation_year", "cgpa"):
        setattr(record, name, _coerce_field_value(data.get(name)))

    record.skills = _coerce_field_value_list(data.get("skills"))
    record.certifications = _coerce_field_value_list(data.get("certifications"))
    record.projects = _coerce_projects(data.get("projects"))
    record.experience = _coerce_experience(data.get("experience"))
    record.additional_fields = _coerce_additional_fields(data.get("additional_fields"))

    return record


def _as_str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _clean_confidence(value: Any) -> Optional[str]:
    return value if value in _VALID_CONFIDENCE else None


def _coerce_field_value(raw: Any) -> Optional[FieldValue]:
    if not isinstance(raw, dict):
        return None
    try:
        return FieldValue(
            raw_value=_as_str_or_none(raw.get("raw_value")),
            normalized_value=None,
            scale=None,
            confidence=_clean_confidence(raw.get("confidence")),
            evidence=_as_str_or_none(raw.get("evidence")),
            assumption=None,
        )
    except Exception:
        return None


def _coerce_field_value_list(raw_list: Any) -> List[FieldValue]:
    if not isinstance(raw_list, list):
        return []
    results = []
    for item in raw_list:
        field_value = _coerce_field_value(item)
        if field_value is not None:
            results.append(field_value)
    return results


def _coerce_projects(raw_list: Any) -> List[ProjectEntry]:
    if not isinstance(raw_list, list):
        return []
    results = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            results.append(
                ProjectEntry(
                    title=_as_str_or_none(item.get("title")),
                    one_liner=_as_str_or_none(item.get("one_liner")),
                    evidence=_as_str_or_none(item.get("evidence")),
                    confidence=_clean_confidence(item.get("confidence")),
                )
            )
        except Exception:
            continue
    return results


def _coerce_experience(raw_list: Any) -> List[ExperienceEntry]:
    if not isinstance(raw_list, list):
        return []
    results = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            results.append(
                ExperienceEntry(
                    company=_as_str_or_none(item.get("company")),
                    role=_as_str_or_none(item.get("role")),
                    duration=_as_str_or_none(item.get("duration")),
                    evidence=_as_str_or_none(item.get("evidence")),
                    confidence=_clean_confidence(item.get("confidence")),
                )
            )
        except Exception:
            continue
    return results


def _is_protected_field(field_name: str) -> bool:
    name = field_name.lower()
    return any(keyword in name for keyword in PROTECTED_ATTRIBUTE_KEYWORDS)


def _coerce_additional_fields(raw_list: Any) -> List[AdditionalField]:
    if not isinstance(raw_list, list):
        return []
    results = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        field_name = item.get("field_name")
        if not field_name or not isinstance(field_name, str):
            continue
        if _is_protected_field(field_name):
            continue  # protected attribute: skip silently, never extracted
        try:
            results.append(
                AdditionalField(
                    field_name=field_name,
                    raw_value=_as_str_or_none(item.get("raw_value")),
                    normalized_value=None,
                    data_type=_as_str_or_none(item.get("data_type")),
                    confidence=_clean_confidence(item.get("confidence")),
                    evidence=_as_str_or_none(item.get("evidence")),
                )
            )
        except Exception:
            continue
    return results


def collect_interpret_items(doc_id: str, record: ResumeRecord, interpret_fields: List[str]) -> List[InterpretItem]:
    """Pulls out the scalar fields (e.g. cgpa) whose raw_value needs scale
    disambiguation before it can be trusted as normalized_value."""
    items: List[InterpretItem] = []
    for field_name in interpret_fields:
        field_value = getattr(record, field_name, None)
        if isinstance(field_value, FieldValue) and field_value.raw_value:
            items.append(InterpretItem(doc_id=doc_id, field=field_name, raw_value=field_value.raw_value))
    return items


def _downgrade(confidence: Optional[str]) -> Optional[str]:
    if confidence == "high":
        return "medium"
    if confidence == "medium":
        return "low"
    return confidence  # already "low" or None


def apply_interpretations(records_by_doc_id: Dict[str, ResumeRecord], results: List[InterpretResult]) -> None:
    """Mutates each record in place: fills normalized_value/scale on the
    matching field, downgrades confidence when the interpreter wasn't sure,
    and leaves a human-readable assumption string either way."""
    for result in results:
        record = records_by_doc_id.get(result.doc_id)
        if record is None:
            continue
        field_value = getattr(record, result.field, None)
        if not isinstance(field_value, FieldValue):
            continue

        source_scale = result.scale if result.scale in _VALID_SCALE else "unknown"
        normalized, assumed_scale = normalize_grade(result.value, source_scale)
        if normalized is None:
            field_value.normalized_value = result.value
            field_value.scale = "unknown"
            field_value.confidence = _downgrade(field_value.confidence)
            field_value.assumption = "grade could not be normalized; manual review required"
            continue

        field_value.normalized_value = normalized
        field_value.scale = "cgpa_10"
        was_assumed = source_scale == "unknown"
        if was_assumed or not result.confident:
            field_value.confidence = "low"

        if assumed_scale == "percentage":
            conversion = "percentage divided by 9.5"
        elif assumed_scale == "gpa_4":
            conversion = "4-point GPA multiplied by 2.5"
        else:
            conversion = "10-point CGPA used as-is"

        prefix = "assumed" if was_assumed else "interpreted"
        field_value.assumption = (
            f"{prefix} source scale {assumed_scale}; {conversion}; normalized to 10-point CGPA"
        )


def normalize_grade(value: Any, scale: Optional[str]) -> tuple[Optional[float], str]:
    """Return a 10-point CGPA and the source scale used for conversion.

    Unknown numeric scales use an explicit deterministic assumption:
    0..4 -> GPA/4, >4..10 -> CGPA/10, >10..100 -> percentage.
    """
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None, "unknown"

    source_scale = scale if scale in _VALID_SCALE else "unknown"
    if source_scale == "unknown":
        if 0 <= numeric <= 4:
            source_scale = "gpa_4"
        elif 4 < numeric <= 10:
            source_scale = "cgpa_10"
        elif 10 < numeric <= 100:
            source_scale = "percentage"
        else:
            return None, "unknown"

    if source_scale == "percentage":
        normalized = numeric / 9.5
    elif source_scale == "gpa_4":
        normalized = numeric * 2.5
    elif source_scale == "cgpa_10":
        normalized = numeric
    else:
        return None, "unknown"

    return round(min(max(normalized, 0.0), 10.0), 2), source_scale


def to_cgpa10(value: Any, scale: Optional[str]) -> Any:
    """Normalize a grade for scoring, retaining compatibility with old JSON."""
    normalized, _source_scale = normalize_grade(value, scale)
    return normalized


def run_sanity_checks(record: ResumeRecord) -> List[str]:
    anomalies: List[str] = []

    name_value = record.full_name.raw_value if record.full_name else None
    if not name_value or not name_value.strip():
        anomalies.append("empty_or_missing_name")

    if record.email and record.email.raw_value:
        if not _EMAIL_RE.match(record.email.raw_value.strip()):
            anomalies.append(f"malformed_email:{record.email.raw_value!r}")

    if record.graduation_year and record.graduation_year.raw_value:
        year = _extract_year(record.graduation_year.raw_value)
        if year is None:
            anomalies.append(f"unparseable_graduation_year:{record.graduation_year.raw_value!r}")
        elif not (2015 <= year <= 2035):
            anomalies.append(f"graduation_year_out_of_range:{year}")

    return anomalies


def _extract_year(raw_value: str) -> Optional[int]:
    match = _YEAR_RE.search(raw_value)
    return int(match.group(0)) if match else None
