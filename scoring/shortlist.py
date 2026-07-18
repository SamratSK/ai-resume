"""Slot-aware shortlist assembly. Every candidate ends up in exactly one of
three sections — Shortlist (top `slots` by score), Reserve (score >= cutoff
but outside the slot count), Excluded (below cutoff or Failed parse) —
nothing is ever silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from scoring.jd_loader import JobDescription
from scoring.scorer import ScoredCandidate


@dataclass
class ShortlistResult:
    jd: JobDescription
    cutoff: float
    shortlisted: List[ScoredCandidate] = field(default_factory=list)
    reserve: List[ScoredCandidate] = field(default_factory=list)
    excluded: List[ScoredCandidate] = field(default_factory=list)
    slots_filled_note: Optional[str] = None


def build_shortlist(jd: JobDescription, candidates: List[ScoredCandidate], cutoff: float) -> ShortlistResult:
    scored = [c for c in candidates if c.score is not None]
    unscored = [c for c in candidates if c.score is None]  # Failed parse / load errors

    scored_sorted = sorted(scored, key=lambda c: c.score, reverse=True)

    shortlisted = scored_sorted[: jd.slots]
    remainder = scored_sorted[jd.slots :]

    reserve = [c for c in remainder if c.score >= cutoff]
    excluded = [c for c in remainder if c.score < cutoff] + unscored

    note = None
    if len(shortlisted) < jd.slots:
        note = f"Only {len(shortlisted)}/{jd.slots} slots filled — fewer eligible candidates than slots."

    return ShortlistResult(jd=jd, cutoff=cutoff, shortlisted=shortlisted, reserve=reserve, excluded=excluded, slots_filled_note=note)
