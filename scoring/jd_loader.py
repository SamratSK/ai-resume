"""Loads Job Description JSON files from a folder. A new JD works by
dropping a file in — nothing here names a specific JD or role.

Skill strings may express alternatives ("React.js or Next.js", "Git/GitHub")
using " or " / "/" as separators — any one alternative satisfies that
requirement. Skills that are all independently required (e.g. HTML, CSS,
JavaScript) should be separate list entries, not slash-joined, since a
slash/or is read as OR, not AND. See skill_matcher.split_alternatives.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class JobDescription(BaseModel):
    id: str
    role: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    cgpa_min: float
    slots: int


def load_jds(jds_dir: Path) -> List[JobDescription]:
    jds: List[JobDescription] = []
    for path in sorted(jds_dir.glob("*.json")):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        jds.append(JobDescription.model_validate(data))
    return jds
