"""PDF source discovery, Docling coordinate conversion, and page rendering."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz
from docling_core.types.doc.document import DoclingDocument

from backend import state
from resume_pipeline.provenance import FieldMatch, map_record, provenance_path
from resume_pipeline.schema import ResumeRecord

RENDER_DPI = 150


def find_source_file(doc_id: str, record: ResumeRecord) -> Optional[Path]:
    candidates = [
        state.UPLOADS_DIR / record.file,
        state.UPLOADS_DIR / f"{doc_id}{Path(record.file).suffix}",
        state.REPO_ROOT / "samples" / record.file,
        state.REPO_ROOT / record.file,
    ]
    return next((path for path in candidates if path.is_file()), None)


def build_pages_payload(doc_id: str, record: ResumeRecord) -> Dict[str, Any]:
    source = find_source_file(doc_id, record)
    document_path = provenance_path(state.stage1_config.paths.output_dir, doc_id)
    if record.method != "docling" or source is None or source.suffix.lower() != ".pdf":
        return {"available": False, "reason": "no source view available for this format", "pages": [], "legend": []}
    if not document_path.exists():
        return {"available": False, "reason": "Docling provenance is not available for this resume", "pages": [], "legend": []}

    matches = map_record(record, document_path)
    docling_document = DoclingDocument.load_from_json(document_path)
    with fitz.open(source) as pdf:
        pages = [
            {
                "page": page_number + 1,
                "width": round(page.rect.width * RENDER_DPI / 72),
                "height": round(page.rect.height * RENDER_DPI / 72),
                "image_url": f"/api/resumes/{doc_id}/pages/{page_number + 1}.png",
            }
            for page_number, page in enumerate(pdf)
        ]

    legend = [_legend_entry(match, docling_document, pages) for match in matches]
    return {
        "available": True,
        "reason": None,
        "pages": pages,
        "legend": legend,
    }


def render_page(doc_id: str, record: ResumeRecord, page_number: int, draw_annotations: bool = True) -> bytes:
    source = find_source_file(doc_id, record)
    document_path = provenance_path(state.stage1_config.paths.output_dir, doc_id)
    if source is None or not document_path.exists() or source.suffix.lower() != ".pdf":
        raise FileNotFoundError("Source PDF or Docling provenance is unavailable")

    matches = map_record(record, document_path)
    docling_document = DoclingDocument.load_from_json(document_path)
    with fitz.open(source) as pdf:
        if page_number < 1 or page_number > len(pdf):
            raise IndexError("Page out of range")
        page = pdf[page_number - 1]
        if draw_annotations:
            for match in matches:
                if not match.located or match.page != page_number or match.bbox is None:
                    continue
                rect = _pdf_rect(match, docling_document, page.rect)
                rgb = _hex_rgb(match.color)
                page.draw_rect(
                    rect,
                    color=rgb,
                    fill=rgb,
                    width=1.2,
                    radius=0.08,
                    stroke_opacity=0.9,
                    fill_opacity=0.16,
                    overlay=True,
                )
        pixmap = page.get_pixmap(dpi=RENDER_DPI, alpha=False)
        return pixmap.tobytes("png")


def _legend_entry(match: FieldMatch, document: DoclingDocument, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    data = asdict(match)
    data["bbox"] = list(match.bbox) if match.bbox else None
    data["rendered_bbox"] = None
    if match.located and match.page and match.bbox and match.page <= len(pages):
        doc_page = document.pages.get(match.page)
        if doc_page:
            rendered = _top_left_bbox(match, float(doc_page.size.width), float(doc_page.size.height))
            scale_x = pages[match.page - 1]["width"] / float(doc_page.size.width)
            scale_y = pages[match.page - 1]["height"] / float(doc_page.size.height)
            data["rendered_bbox"] = [
                round(rendered[0] * scale_x, 2),
                round(rendered[1] * scale_y, 2),
                round(rendered[2] * scale_x, 2),
                round(rendered[3] * scale_y, 2),
            ]
    return data


def _pdf_rect(match: FieldMatch, document: DoclingDocument, pdf_rect: fitz.Rect) -> fitz.Rect:
    doc_page = document.pages.get(match.page or 1)
    if doc_page is None:
        raise ValueError("Docling page metadata missing")
    box = _top_left_bbox(match, float(doc_page.size.width), float(doc_page.size.height))
    scale_x = pdf_rect.width / float(doc_page.size.width)
    scale_y = pdf_rect.height / float(doc_page.size.height)
    return fitz.Rect(box[0] * scale_x, box[1] * scale_y, box[2] * scale_x, box[3] * scale_y)


def _top_left_bbox(match: FieldMatch, width: float, height: float) -> Tuple[float, float, float, float]:
    del width
    if match.bbox is None:
        raise ValueError("Match has no bounding box")
    left, top, right, bottom = match.bbox
    # Docling PDF provenance uses bottom-left coordinates.
    if top > bottom:
        return left, height - top, right, height - bottom
    return left, top, right, bottom


def _hex_rgb(value: str) -> Tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
