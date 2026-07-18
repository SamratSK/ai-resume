"""Orchestrates the per-file pipeline: router -> quality -> extraction ->
merge -> (batched) interpretation -> report. Every file gets its own
try/except so one bad file can never take down the whole batch, and every
file — parsed or not — ends up in the report.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from resume_pipeline import merge, quality, router
from resume_pipeline.config import PipelineConfig
from resume_pipeline.docling_wrapper import DoclingExtractor
from resume_pipeline.extraction_client import extract_fields
from resume_pipeline.interpreter_client import interpret_values
from resume_pipeline.model_client import LLMClient
from resume_pipeline.report import ReportRow, write_report
from resume_pipeline.schema import ResumeRecord

_ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_\-]")


def run_pipeline(folder: Path, config: PipelineConfig) -> List[ReportRow]:
    docling_extractor = DoclingExtractor(config.docling)  # loaded once, reused for every file
    extraction_llm = LLMClient(config.extraction)
    interpretation_llm = LLMClient(config.interpretation)

    try:
        files = sorted(p for p in folder.iterdir() if p.is_file())
        records_by_doc_id: Dict[str, ResumeRecord] = {}
        report_rows: List[ReportRow] = []
        used_ids: Dict[str, int] = {}

        for file_path in files:
            doc_id = _make_doc_id(file_path, used_ids)
            try:
                provenance_path = config.paths.output_dir / "provenance" / f"{doc_id}.docling.json"
                record, notes = _process_file(
                    file_path,
                    docling_extractor,
                    extraction_llm,
                    provenance_path,
                )
            except Exception as exc:  # last-resort net: one bad file never kills the batch
                record = ResumeRecord(file=file_path.name, method="unsupported", parse_quality="Failed")
                record.anomalies = [f"unexpected_error:{exc}"]
                notes = f"unexpected_error:{exc}"

            records_by_doc_id[doc_id] = record
            report_rows.append(
                ReportRow(
                    file=str(file_path.relative_to(folder)),
                    method=record.method,
                    parse_quality=record.parse_quality,
                    anomaly_count=len(record.anomalies),
                    notes=notes,
                )
            )

        _run_interpretation(records_by_doc_id, interpretation_llm, config.interpret_fields)

        config.paths.output_dir.mkdir(parents=True, exist_ok=True)
        for doc_id, record in records_by_doc_id.items():
            out_path = config.paths.output_dir / f"{doc_id}.json"
            out_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        write_report(report_rows, config.paths.report_path)
        return report_rows
    finally:
        extraction_llm.close()
        interpretation_llm.close()


def _process_file(
    file_path: Path,
    docling_extractor: DoclingExtractor,
    extraction_llm: LLMClient,
    document_json_path: Optional[Path] = None,
) -> Tuple[ResumeRecord, Optional[str]]:
    try:
        text, method = router.extract_text(file_path, docling_extractor, document_json_path)
    except router.ParseFailure as exc:
        record = merge.build_record(file_path.name, exc.method, "Failed", None)
        record.anomalies = [f"parse_failed:{exc.reason}"]
        return record, f"Failed Parse: {exc.reason}"

    quality_assessment = quality.assess_parse_quality(text)
    parse_quality = quality_assessment.quality
    notes_parts: List[str] = list(quality_assessment.reasons)

    extraction_data = None
    if parse_quality == "Failed":
        notes_parts.append("extraction_skipped:text_quality_failed")
    else:
        outcome = extract_fields(extraction_llm, text)
        if outcome.success:
            extraction_data = outcome.data
        else:
            parse_quality = _downgrade_quality(parse_quality)
            notes_parts.append(f"extraction_failed:{outcome.error}")

    record = merge.build_record(file_path.name, method, parse_quality, extraction_data)
    record.anomalies = merge.run_sanity_checks(record)

    return record, "; ".join(notes_parts) if notes_parts else None


def _run_interpretation(
    records_by_doc_id: Dict[str, ResumeRecord], interpretation_llm: LLMClient, interpret_fields: List[str]
) -> None:
    items = []
    for doc_id, record in records_by_doc_id.items():
        items.extend(merge.collect_interpret_items(doc_id, record, interpret_fields))
    if not items:
        return
    results = interpret_values(interpretation_llm, items)
    merge.apply_interpretations(records_by_doc_id, results)


def _downgrade_quality(current: str) -> str:
    return "Partial" if current == "Clean" else "Failed"


def _make_doc_id(file_path: Path, used_ids: Dict[str, int]) -> str:
    base = _ID_SANITIZE_RE.sub("_", file_path.stem) or "file"
    if base not in used_ids:
        used_ids[base] = 0
        return base
    used_ids[base] += 1
    return f"{base}_{used_ids[base]}"
