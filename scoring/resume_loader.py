"""Loads Stage 1 outputs (extracted/<resume_name>.json) back into
ResumeRecord objects — reuses Stage 1's schema directly rather than
duplicating the field/evidence shape.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from pydantic import ValidationError

from resume_pipeline.schema import ResumeRecord


@dataclass
class LoadError:
    file_name: str
    reason: str


def load_resumes(resumes_dir: Path) -> Tuple[List[Tuple[str, ResumeRecord]], List[LoadError]]:
    """Returns (doc_id, ResumeRecord) pairs plus any files that couldn't be
    loaded at all — the latter are never silently dropped; scorer.py surfaces
    them as human-review-required entries so every input file still appears
    somewhere in the output."""
    records: List[Tuple[str, ResumeRecord]] = []
    errors: List[LoadError] = []

    for path in sorted(resumes_dir.glob("*.json")):
        doc_id = path.stem
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            record = ResumeRecord.model_validate(data)
        except (json.JSONDecodeError, ValidationError, OSError) as exc:
            errors.append(LoadError(file_name=path.name, reason=str(exc)))
            continue
        records.append((doc_id, record))

    return records, errors
