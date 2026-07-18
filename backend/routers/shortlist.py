"""Runs (or re-runs against a warm cache) Stage 2 scoring for one JD.

Scoring is a background job — first-run scoring can take a while (multiple
batched LLM calls); the frontend polls GET /api/jobs/{id}. The result is
also persisted to output/ so the CSV export endpoint has something to read
without recomputing.
"""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import state
from backend.jobs import Job, job_manager
from backend.routers.jds import _jd_path
from scoring.jd_loader import JobDescription
from scoring.output_writer import build_shortlist_payload, write_jd_outputs
from scoring.resume_loader import load_resumes
from scoring.scorer import ScoredCandidate, score_jd
from scoring.shortlist import build_shortlist

router = APIRouter(prefix="/api/jds", tags=["shortlist"])


class ShortlistStartedResponse(BaseModel):
    job_id: str


def _load_jd(jd_id: str) -> JobDescription:
    path = _jd_path(jd_id)
    if not path.exists():
        raise HTTPException(404, f"JD '{jd_id}' not found")
    return JobDescription.model_validate(json.loads(path.read_text(encoding="utf-8")))


@router.get("/{jd_id}/shortlist", response_model=ShortlistStartedResponse, status_code=202)
def start_shortlist(jd_id: str) -> ShortlistStartedResponse:
    jd = _load_jd(jd_id)

    def _run(job: Job):
        records, load_errors = load_resumes(state.stage1_config.paths.output_dir)
        job.progress = f"Scoring {len(records)} candidate(s) against {jd.role}..."
        candidates = score_jd(jd, records, state.scoring_llm, state.scoring_cache, state.scoring_config)
        for load_error in load_errors:
            candidates.append(
                ScoredCandidate(
                    doc_id=load_error.file_name,
                    file=load_error.file_name,
                    parse_quality="Failed",
                    human_review_required=True,
                    anomalies=[f"load_failed:{load_error.reason}"],
                    error=load_error.reason,
                )
            )
        shortlist_result = build_shortlist(jd, candidates, state.scoring_config.shortlist.score_cutoff)
        write_jd_outputs(shortlist_result, state.scoring_config.paths.output_dir)
        job.progress = "Done"
        return build_shortlist_payload(shortlist_result)

    job_id = job_manager.start(_run)
    return ShortlistStartedResponse(job_id=job_id)


@router.get("/{jd_id}/shortlist.csv")
def shortlist_csv(jd_id: str) -> StreamingResponse:
    path = state.scoring_config.paths.output_dir / f"{jd_id}_shortlist.json"
    if not path.exists():
        raise HTTPException(404, f"No shortlist computed yet for '{jd_id}' — run scoring first")
    payload = json.loads(path.read_text(encoding="utf-8"))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "rank", "file", "score", "confidence", "parse_quality", "human_review_required"])
    for section in ("shortlist", "reserve", "excluded"):
        for c in payload.get(section, []):
            writer.writerow(
                [section, c.get("rank"), c.get("file"), c.get("score"), c.get("confidence"), c.get("parse_quality"), c.get("human_review_required")]
            )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={jd_id}_shortlist.csv"},
    )
