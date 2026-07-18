"""Map extracted evidence quotes to Docling text-item provenance."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple

from docling_core.types.doc.document import DoclingDocument
from rapidfuzz import fuzz

from resume_pipeline.schema import ResumeRecord, SCALAR_FIELD_NAMES

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s.+#/@-]", re.UNICODE)

GROUP_COLORS = {
    "identity": "#9B8AFB",
    "education": "#58C9A7",
    "skills": "#F0A66E",
    "projects": "#E77D96",
    "experience": "#6FA7E8",
    "certifications": "#C294D8",
    "additional": "#A1A7B3",
}


@dataclass(frozen=True)
class EvidenceField:
    field: str
    label: str
    group: str
    evidence: str


@dataclass(frozen=True)
class TextBox:
    text: str
    page: int
    bbox: Tuple[float, float, float, float]
    origin: str


@dataclass(frozen=True)
class FieldMatch:
    field: str
    label: str
    group: str
    color: str
    located: bool
    page: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None
    score: Optional[float] = None


def provenance_path(output_dir: Path, doc_id: str) -> Path:
    return output_dir / "provenance" / f"{doc_id}.docling.json"


def iter_evidence_fields(record: ResumeRecord) -> Iterator[EvidenceField]:
    for name in SCALAR_FIELD_NAMES:
        value = getattr(record, name)
        if value and value.evidence:
            group = "identity" if name in {"full_name", "email", "phone"} else "education"
            yield EvidenceField(name, name.replace("_", " ").title(), group, value.evidence)

    for index, value in enumerate(record.skills):
        if value.evidence:
            yield EvidenceField(
                f"skills.{index}",
                value.raw_value or f"Skill {index + 1}",
                "skills",
                value.evidence,
            )
    for index, value in enumerate(record.projects):
        if value.evidence:
            yield EvidenceField(
                f"projects.{index}",
                value.title or f"Project {index + 1}",
                "projects",
                value.evidence,
            )
    for index, value in enumerate(record.experience):
        if value.evidence:
            label = " at ".join(part for part in (value.role, value.company) if part)
            yield EvidenceField(f"experience.{index}", label or f"Experience {index + 1}", "experience", value.evidence)
    for index, value in enumerate(record.certifications):
        if value.evidence:
            yield EvidenceField(
                f"certifications.{index}",
                value.raw_value or f"Certification {index + 1}",
                "certifications",
                value.evidence,
            )
    for index, value in enumerate(record.additional_fields):
        if value.evidence:
            yield EvidenceField(f"additional_fields.{index}", value.field_name, "additional", value.evidence)


def map_record(record: ResumeRecord, document_path: Path, threshold: float = 85.0) -> List[FieldMatch]:
    document = DoclingDocument.load_from_json(document_path)
    boxes = list(_iter_text_boxes(document))
    matches: List[FieldMatch] = []
    for field in iter_evidence_fields(record):
        try:
            match = _find_best(field, boxes, threshold)
        except Exception:
            match = None
        if match is None:
            matches.append(
                FieldMatch(
                    field=field.field,
                    label=field.label,
                    group=field.group,
                    color=GROUP_COLORS[field.group],
                    located=False,
                )
            )
        else:
            page, bbox, score = match
            matches.append(
                FieldMatch(
                    field=field.field,
                    label=field.label,
                    group=field.group,
                    color=GROUP_COLORS[field.group],
                    located=True,
                    page=page,
                    bbox=bbox,
                    score=round(score, 2),
                )
            )
    return matches


def _iter_text_boxes(document: DoclingDocument) -> Iterable[TextBox]:
    for item, _level in document.iterate_items():
        text = getattr(item, "text", None)
        if not text:
            continue
        for prov in getattr(item, "prov", []) or []:
            bbox = prov.bbox
            origin = getattr(bbox.coord_origin, "value", str(bbox.coord_origin))
            yield TextBox(
                text=text,
                page=int(prov.page_no),
                bbox=(float(bbox.l), float(bbox.t), float(bbox.r), float(bbox.b)),
                origin=origin,
            )


def _find_best(
    field: EvidenceField,
    boxes: List[TextBox],
    threshold: float,
) -> Optional[Tuple[int, Tuple[float, float, float, float], float]]:
    needle = _normalize(field.evidence)
    if not needle:
        return None

    best: Optional[Tuple[int, Tuple[float, float, float, float], float]] = None
    for start, first in enumerate(boxes):
        same_page: List[TextBox] = []
        for candidate in boxes[start : start + 3]:
            if candidate.page != first.page:
                break
            same_page.append(candidate)
            haystack = _normalize(" ".join(box.text for box in same_page))
            if not haystack:
                continue
            score = max(fuzz.ratio(needle, haystack), fuzz.partial_ratio(needle, haystack))
            if best is None or score > best[2]:
                best = (first.page, _union_boxes(same_page), score)

    return best if best and best[2] >= threshold else None


def _union_boxes(boxes: List[TextBox]) -> Tuple[float, float, float, float]:
    left = min(box.bbox[0] for box in boxes)
    right = max(box.bbox[2] for box in boxes)
    if boxes[0].origin.upper().endswith("BOTTOMLEFT"):
        top = max(box.bbox[1] for box in boxes)
        bottom = min(box.bbox[3] for box in boxes)
    else:
        top = min(box.bbox[1] for box in boxes)
        bottom = max(box.bbox[3] for box in boxes)
    return left, top, right, bottom


def _normalize(value: str) -> str:
    value = html.unescape(value).lower().replace("\u00a0", " ")
    value = _NON_WORD_RE.sub(" ", value)
    return _SPACE_RE.sub(" ", value).strip()
