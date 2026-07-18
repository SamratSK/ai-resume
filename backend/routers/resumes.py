"""Resume upload (runs Stage 1), list, detail, delete.

Upload is a background job (Stage 1 extraction is slow — Docling + an LLM
call per file) — the endpoint saves the files synchronously, then hands
off to a job the frontend polls via GET /api/jobs/{id}.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend import state
from backend.jobs import Job, job_manager
from resume_pipeline.pipeline import _make_doc_id, _process_file
from resume_pipeline.provenance import provenance_path
from resume_pipeline.schema import ResumeRecord

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


class ResumeSummary(BaseModel):
    doc_id: str
    file: str
    method: str
    parse_quality: str
    anomaly_count: int


class UploadStartedResponse(BaseModel):
    job_id: str


def _extracted_path(doc_id: str) -> Path:
    return state.stage1_config.paths.output_dir / f"{doc_id}.json"


def _existing_doc_ids() -> dict:
    used = {}
    for path in state.stage1_config.paths.output_dir.glob("*.json"):
        used[path.stem] = 0
    return used


@router.get("", response_model=List[ResumeSummary])
def list_resumes() -> List[ResumeSummary]:
    summaries = []
    for path in sorted(state.stage1_config.paths.output_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        summaries.append(
            ResumeSummary(
                doc_id=path.stem,
                file=data.get("file", path.stem),
                method=data.get("method", "unsupported"),
                parse_quality=data.get("parse_quality", "Failed"),
                anomaly_count=len(data.get("anomalies", [])),
            )
        )
    return summaries


@router.get("/{doc_id}", response_model=ResumeRecord)
def get_resume(doc_id: str) -> ResumeRecord:
    path = _extracted_path(doc_id)
    if not path.exists():
        raise HTTPException(404, f"Resume '{doc_id}' not found")
    return ResumeRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


@router.get("/{doc_id}/pages")
def get_resume_pages(doc_id: str):
    record = get_resume(doc_id)
    from backend.provenance import build_pages_payload

    return build_pages_payload(doc_id, record)


@router.get("/{doc_id}/pages/{page_number}.png")
def get_resume_page_image(doc_id: str, page_number: int, annotations: bool = True) -> Response:
    record = get_resume(doc_id)
    from backend.provenance import render_page

    try:
        png = render_page(doc_id, record, page_number, draw_annotations=annotations)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(content=png, media_type="image/png")


@router.delete("/{doc_id}", status_code=204)
def delete_resume(doc_id: str) -> None:
    path = _extracted_path(doc_id)
    if not path.exists():
        raise HTTPException(404, f"Resume '{doc_id}' not found")
    path.unlink()
    docling_path = provenance_path(state.stage1_config.paths.output_dir, doc_id)
    if docling_path.exists():
        docling_path.unlink()
    markdown_path = docling_path.with_name(docling_path.name.removesuffix(".docling.json") + ".md")
    if markdown_path.exists():
        markdown_path.unlink()
    try:
        state.chat_service.delete_resume(doc_id)
    except Exception:
        pass
    for source in state.UPLOADS_DIR.glob(f"{doc_id}.*"):
        source.unlink()


@router.post("", response_model=UploadStartedResponse, status_code=202)
async def upload_resumes(files: List[UploadFile]) -> UploadStartedResponse:
    if not files:
        raise HTTPException(400, "No files provided")

    saved_paths: List[Path] = []
    for upload in files:
        if not upload.filename:
            continue
        dest = state.UPLOADS_DIR / upload.filename
        with open(dest, "wb") as out:
            shutil.copyfileobj(upload.file, out)
        saved_paths.append(dest)

    if not saved_paths:
        raise HTTPException(400, "No valid files provided")

    def _run(job: Job) -> List[ResumeSummary]:
        used_ids = _existing_doc_ids()
        results: List[ResumeSummary] = []
        for i, file_path in enumerate(saved_paths, start=1):
            job.progress = f"Processing {i}/{len(saved_paths)}: {file_path.name}"
            doc_id = _make_doc_id(file_path, used_ids)
            try:
                record, _notes = _process_file(
                    file_path,
                    state.docling_extractor,
                    state.extraction_llm,
                    provenance_path(state.stage1_config.paths.output_dir, doc_id),
                )
            except Exception as exc:
                record = ResumeRecord(file=file_path.name, method="unsupported", parse_quality="Failed")
                record.anomalies = [f"unexpected_error:{exc}"]

            if record.cgpa and record.cgpa.raw_value:
                from resume_pipeline.interpreter_client import interpret_values
                from resume_pipeline.merge import apply_interpretations, collect_interpret_items

                items = collect_interpret_items(doc_id, record, state.stage1_config.interpret_fields)
                if items:
                    interp_results = interpret_values(state.interpretation_llm, items)
                    apply_interpretations({doc_id: record}, interp_results)

            _extracted_path(doc_id).write_text(record.model_dump_json(indent=2), encoding="utf-8")
            try:
                state.chat_service.index_resume(doc_id, record)
            except Exception:
                # Extraction remains successful if the independent embedding service is unavailable.
                pass
            results.append(
                ResumeSummary(
                    doc_id=doc_id,
                    file=record.file,
                    method=record.method,
                    parse_quality=record.parse_quality,
                    anomaly_count=len(record.anomalies),
                )
            )
        job.progress = f"Done — processed {len(results)} file(s)"
        return results

    job_id = job_manager.start(_run)
    return UploadStartedResponse(job_id=job_id)
