"""Mechanical (pure Python, deterministic) scoring components: required
skills, preferred skills, CGPA. No LLM calls happen in this module.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from resume_pipeline.merge import to_cgpa10
from resume_pipeline.schema import FieldValue
from scoring.skill_matcher import SkillMatch


class ComponentResult(BaseModel):
    points: float
    max_points: float
    source: str  # "python" | "llm"
    detail: str
    meta: Optional[Dict[str, Any]] = None  # LLM-only extras: justification, signals, fallback_used, etc.


def required_skills_score(matches: List[SkillMatch], max_points: float) -> ComponentResult:
    return _skill_component_score(matches, max_points, "required")


def preferred_skills_score(matches: List[SkillMatch], max_points: float) -> ComponentResult:
    return _skill_component_score(matches, max_points, "preferred")


def _skill_component_score(matches: List[SkillMatch], max_points: float, label: str) -> ComponentResult:
    if not matches:
        return ComponentResult(
            points=max_points,
            max_points=max_points,
            source="python",
            detail=f"JD lists no {label} skills; full points by default.",
        )
    total_credit = sum(m.credit for m in matches)
    fraction = total_credit / len(matches)
    points = round(max_points * fraction, 2)

    tier_counts: Dict[str, int] = {}
    for m in matches:
        tier_counts[m.tier] = tier_counts.get(m.tier, 0) + 1
    tier_summary = ", ".join(f"{count} {tier}" for tier, count in tier_counts.items() if count)

    detail = (
        f"{label} skills ({len(matches)} total): {tier_summary} "
        f"— credit-weighted {total_credit:.2f}/{len(matches)} (exact/synonym=full credit, "
        f"partial=half, implicit=quarter, missing=zero) -> {points}/{max_points} points"
    )
    return ComponentResult(points=points, max_points=max_points, source="python", detail=detail)


def cgpa_score(cgpa_field: Optional[FieldValue], cgpa_min: float, max_points: float, scale_window: float) -> ComponentResult:
    if cgpa_field is None or not cgpa_field.raw_value:
        return ComponentResult(points=0.0, max_points=max_points, source="python", detail="CGPA not found on resume -> 0 points.")

    if cgpa_field.scale in (None, "unknown") or cgpa_field.normalized_value is None:
        return ComponentResult(
            points=0.0,
            max_points=max_points,
            source="python",
            detail=f"CGPA scale unknown (raw={cgpa_field.raw_value!r}) -> 0 points, flagged for manual review.",
        )

    converted = to_cgpa10(cgpa_field.normalized_value, cgpa_field.scale)
    try:
        value = float(converted)
    except (TypeError, ValueError):
        return ComponentResult(
            points=0.0,
            max_points=max_points,
            source="python",
            detail=f"CGPA normalized_value not numeric ({converted!r}) -> 0 points.",
        )

    scale_note = "" if cgpa_field.scale == "cgpa_10" else f" [normalized from {cgpa_field.scale}]"

    if value >= cgpa_min:
        return ComponentResult(
            points=max_points,
            max_points=max_points,
            source="python",
            detail=f"CGPA {value}{scale_note} meets minimum {cgpa_min} -> full {max_points} points.",
        )

    floor = cgpa_min - scale_window
    if value <= floor:
        return ComponentResult(
            points=0.0,
            max_points=max_points,
            source="python",
            detail=f"CGPA {value}{scale_note} at/below floor {floor} (min {cgpa_min} - {scale_window}) -> 0 points.",
        )

    fraction = (value - floor) / (cgpa_min - floor)
    points = round(max_points * fraction, 2)
    return ComponentResult(
        points=points,
        max_points=max_points,
        source="python",
        detail=f"CGPA {value}{scale_note} linearly scaled between floor {floor} and min {cgpa_min} -> {points}/{max_points} points.",
    )
