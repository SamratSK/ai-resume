"""Polling endpoint for background jobs started by resumes/shortlist routers."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.jobs import job_manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    id: str
    status: str  # pending | running | done | error
    progress: str
    result: Any = None
    error: Optional[str] = None


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return JobStatusResponse(id=job.id, status=job.status, progress=job.progress, result=job.result, error=job.error)
