"""JD CRUD — reads/writes the exact same JSON files in jds/ that the
scoring engine reads. No separate database; the folder is the store.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import state
from backend.jd_parser import parse_job_description
from scoring.jd_loader import JobDescription, load_jds

router = APIRouter(prefix="/api/jds", tags=["jds"])


class JDCreateRequest(BaseModel):
    id: str
    role: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    cgpa_min: float
    slots: int


class JDUpdateRequest(BaseModel):
    role: Optional[str] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    cgpa_min: Optional[float] = None
    slots: Optional[int] = None


class JDParseRequest(BaseModel):
    text: str = Field(min_length=20)


def _slugify_role(role: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", role.casefold()).strip("_")
    return slug or "parsed_jd"


def _jd_path(jd_id: str):
    return state.scoring_config.paths.jds_dir / f"{jd_id}.json"


@router.get("", response_model=List[JobDescription])
def list_jds() -> List[JobDescription]:
    return load_jds(state.scoring_config.paths.jds_dir)


@router.post("/parse", response_model=JobDescription)
def parse_jd(payload: JDParseRequest) -> JobDescription:
    """Bonus C: parse a pasted posting without persisting it."""
    try:
        parsed = parse_job_description(state.extraction_llm, payload.text)
    except Exception as exc:
        raise HTTPException(502, f"Could not parse the job description: {exc}") from exc
    return JobDescription(id=_slugify_role(parsed["role"]), **parsed)


@router.get("/{jd_id}", response_model=JobDescription)
def get_jd(jd_id: str) -> JobDescription:
    path = _jd_path(jd_id)
    if not path.exists():
        raise HTTPException(404, f"JD '{jd_id}' not found")
    return JobDescription.model_validate(json.loads(path.read_text(encoding="utf-8")))


@router.post("", response_model=JobDescription, status_code=201)
def create_jd(payload: JDCreateRequest) -> JobDescription:
    path = _jd_path(payload.id)
    if path.exists():
        raise HTTPException(409, f"JD '{payload.id}' already exists")
    jd = JobDescription.model_validate(payload.model_dump())
    path.write_text(jd.model_dump_json(indent=2), encoding="utf-8")
    return jd


@router.put("/{jd_id}", response_model=JobDescription)
def update_jd(jd_id: str, payload: JDUpdateRequest) -> JobDescription:
    path = _jd_path(jd_id)
    if not path.exists():
        raise HTTPException(404, f"JD '{jd_id}' not found")
    existing = JobDescription.model_validate(json.loads(path.read_text(encoding="utf-8")))
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    merged = existing.model_copy(update=updates)
    path.write_text(merged.model_dump_json(indent=2), encoding="utf-8")
    return merged


@router.delete("/{jd_id}", status_code=204)
def delete_jd(jd_id: str) -> None:
    path = _jd_path(jd_id)
    if not path.exists():
        raise HTTPException(404, f"JD '{jd_id}' not found")
    path.unlink()
    for suffix in ("_shortlist.json", "_shortlist.md"):
        stale = state.scoring_config.paths.output_dir / f"{jd_id}{suffix}"
        if stale.exists():
            stale.unlink()
