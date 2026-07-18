"""Writes parse_quality_report.md — every input file must appear here,
regardless of whether it succeeded, so a bad file is always visible rather
than silently dropped from the batch.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class ReportRow:
    file: str
    method: str
    parse_quality: str  # "Clean" | "Partial" | "Failed"
    anomaly_count: int
    notes: Optional[str] = None  # what failed / degraded, in plain words


def write_report(rows: List[ReportRow], report_path: Path) -> None:
    counts = Counter(row.parse_quality for row in rows)

    lines = [
        "# Parse Quality Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        f"Total files: {len(rows)}",
        f"- Clean: {counts.get('Clean', 0)}",
        f"- Partial: {counts.get('Partial', 0)}",
        f"- Failed: {counts.get('Failed', 0)}",
        "",
        "| File | Method | Parse Quality | Anomalies | Notes |",
        "|---|---|---|---|---|",
    ]

    for row in sorted(rows, key=lambda r: r.file):
        lines.append(
            f"| {_md_escape(row.file)} | {row.method} | {row.parse_quality} | "
            f"{row.anomaly_count} | {_md_escape(row.notes or '')} |"
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()
