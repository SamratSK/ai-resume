"""Per-candidate confidence, capped by Stage 1's parse_quality — a separate
axis from the score itself. Confidence never gets to claim more certainty
than the underlying extraction earned.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from resume_pipeline.schema import ResumeRecord
from scoring.skill_matcher import SkillMatch


@dataclass
class ConfidenceResult:
    confidence: Optional[str]  # "High" | "Medium" | "Low" | None (Failed parse)
    human_review_required: bool
    reasons: List[str]


def compute_confidence(record: ResumeRecord, skill_matches: List[SkillMatch]) -> ConfidenceResult:
    if record.parse_quality == "Failed":
        return ConfidenceResult(confidence=None, human_review_required=True, reasons=["parse_quality is Failed"])

    if record.parse_quality == "Partial":
        return ConfidenceResult(confidence="Medium", human_review_required=False, reasons=["parse_quality is Partial -> capped at Medium"])

    # Clean parse: start High, downgrade to Medium if warranted.
    reasons: List[str] = []
    downgrade = False

    if record.cgpa is not None and record.cgpa.confidence == "low":
        downgrade = True
        reasons.append("CGPA field extraction confidence is low")

    matched_skill_values = {m.matched_against for m in skill_matches if m.matched_against}
    low_confidence_matched_skills = [
        s.raw_value for s in record.skills if s.raw_value in matched_skill_values and s.confidence == "low"
    ]
    if low_confidence_matched_skills:
        downgrade = True
        reasons.append(f"low-confidence extraction on matched skill(s): {', '.join(low_confidence_matched_skills)}")

    total_credit = sum(m.credit for m in skill_matches)
    implicit_credit = sum(m.credit for m in skill_matches if m.tier == "implicit")
    if total_credit > 0 and (implicit_credit / total_credit) > 0.5:
        downgrade = True
        reasons.append("implicit-tier matches account for more than half of matched skill credit")

    if downgrade:
        return ConfidenceResult(confidence="Medium", human_review_required=False, reasons=reasons)

    return ConfidenceResult(confidence="High", human_review_required=False, reasons=["Clean parse, no low-confidence key fields, no implicit-match dominance"])
