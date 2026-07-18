"""Writes per-JD shortlist.json / shortlist.md, and the aggregate
output/summary.md. Nothing else in the package touches the filesystem for
results — this is the single place output shape lives.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from scoring.scorer import ScoredCandidate
from scoring.shortlist import ShortlistResult


@dataclass
class JdSummaryLine:
    jd_id: str
    role: str
    candidates_evaluated: int
    shortlisted: int
    cutoff: float
    parse_failures: int


def build_shortlist_payload(result: ShortlistResult) -> Dict[str, Any]:
    """Public entry point for callers (e.g. the API) that want the same
    ranked/sectioned JSON shape write_jd_outputs persists, without writing
    files themselves."""
    return _build_json_payload(result, _assign_ranks(result))


def write_jd_outputs(result: ShortlistResult, output_dir: Path) -> JdSummaryLine:
    output_dir.mkdir(parents=True, exist_ok=True)

    sections = _assign_ranks(result)
    payload = _build_json_payload(result, sections)

    (output_dir / f"{result.jd.id}_shortlist.json").write_text(
        json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8"
    )
    (output_dir / f"{result.jd.id}_shortlist.md").write_text(_build_markdown(result, sections), encoding="utf-8")

    parse_failures = sum(1 for c in result.excluded if c.parse_quality == "Failed")
    total = len(result.shortlisted) + len(result.reserve) + len(result.excluded)
    return JdSummaryLine(
        jd_id=result.jd.id,
        role=result.jd.role,
        candidates_evaluated=total,
        shortlisted=len(result.shortlisted),
        cutoff=result.cutoff,
        parse_failures=parse_failures,
    )


def write_summary_md(lines: List[JdSummaryLine], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    md_lines = [
        "# Stage 2 Scoring Summary",
        "",
        "| JD | Role | Evaluated | Shortlisted | Cutoff | Parse Failures |",
        "|---|---|---|---|---|---|",
    ]
    for line in lines:
        md_lines.append(
            f"| {line.jd_id} | {line.role} | {line.candidates_evaluated} | {line.shortlisted} | {line.cutoff} | {line.parse_failures} |"
        )
    (output_dir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def _assign_ranks(result: ShortlistResult) -> Dict[str, List[Dict[str, Any]]]:
    rank = 1
    sections: Dict[str, List[Dict[str, Any]]] = {"shortlist": [], "reserve": [], "excluded": []}

    for candidate in result.shortlisted:
        sections["shortlist"].append(_candidate_entry(candidate, rank))
        rank += 1
    for candidate in result.reserve:
        sections["reserve"].append(_candidate_entry(candidate, rank))
        rank += 1
    for candidate in result.excluded:
        if candidate.score is not None:
            sections["excluded"].append(_candidate_entry(candidate, rank))
            rank += 1
        else:
            sections["excluded"].append(_candidate_entry(candidate, None))

    return sections


def _candidate_entry(candidate: ScoredCandidate, rank: Optional[int]) -> Dict[str, Any]:
    return {"rank": rank, **candidate.model_dump()}


def _build_json_payload(result: ShortlistResult, sections: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    return {
        "jd_id": result.jd.id,
        "role": result.jd.role,
        "slots": result.jd.slots,
        "cutoff": result.cutoff,
        "candidates_evaluated": len(result.shortlisted) + len(result.reserve) + len(result.excluded),
        "slots_filled_note": result.slots_filled_note,
        "shortlist": sections["shortlist"],
        "reserve": sections["reserve"],
        "excluded": sections["excluded"],
    }


def _build_markdown(result: ShortlistResult, sections: Dict[str, List[Dict[str, Any]]]) -> str:
    total = len(result.shortlisted) + len(result.reserve) + len(result.excluded)
    lines = [
        f"# {result.jd.role} — Shortlist ({result.jd.id})",
        "",
        f"Slots: {result.jd.slots} | Cutoff: {result.cutoff} | Evaluated: {total}",
        "",
    ]
    if result.slots_filled_note:
        lines.append(f"> {result.slots_filled_note}")
        lines.append("")

    lines.append("## Shortlist")
    lines.append("")
    if not sections["shortlist"]:
        lines.append("_No candidates shortlisted._")
        lines.append("")
    for entry in sections["shortlist"]:
        lines.extend(_render_candidate_md(entry))

    lines.append("## Reserve")
    lines.append("")
    if not sections["reserve"]:
        lines.append("_No candidates in reserve._")
        lines.append("")
    for entry in sections["reserve"]:
        lines.extend(_render_candidate_md(entry))

    lines.append("## Excluded")
    lines.append("")
    if not sections["excluded"]:
        lines.append("_No excluded candidates._")
        lines.append("")
    for entry in sections["excluded"]:
        lines.extend(_render_candidate_md(entry, compact=True))

    return "\n".join(lines) + "\n"


def _render_candidate_md(entry: Dict[str, Any], compact: bool = False) -> List[str]:
    rank = entry.get("rank")
    rank_str = f"#{rank}" if rank is not None else "unranked"
    score = entry.get("score")
    score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "N/A"

    lines = [f"### {rank_str} — {entry['file']} (score: {score_str}, confidence: {entry.get('confidence') or 'N/A'})", ""]

    if entry.get("human_review_required"):
        lines.append("- **Human review required**")
    if entry.get("error"):
        lines.append(f"- Error: {entry['error']}")

    if compact:
        for anomaly in entry.get("anomalies", []):
            lines.append(f"- Anomaly: {anomaly}")
        lines.append("")
        return lines

    breakdown = entry.get("breakdown") or {}
    if breakdown:
        lines.append("- **Breakdown:**")
        for name, comp in breakdown.items():
            lines.append(f"  - {name} [{comp.get('source')}]: {comp.get('points')}/{comp.get('max_points')} — {comp.get('detail')}")

    for label, key in (("Required skills", "required_skill_matches"), ("Preferred skills", "preferred_skill_matches")):
        matches = entry.get(key) or []
        if matches:
            lines.append(f"- **{label}:**")
            for m in matches:
                flag = " ⚑" if m.get("flagged") else ""
                lines.append(f"  - {m['jd_skill']}: **{m['tier']}**{flag} (matched: {m.get('matched_against') or '—'})")

    bullets = entry.get("reasoning_bullets") or []
    if bullets:
        lines.append("- **Why:**")
        for bullet in bullets:
            lines.append(f"  - {bullet}")

    for anomaly in entry.get("anomalies", []):
        lines.append(f"- Anomaly: {anomaly}")

    lines.append("")
    return lines
