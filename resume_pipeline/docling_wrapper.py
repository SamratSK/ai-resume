"""Thin wrapper around docling's DocumentConverter.

The converter loads layout/OCR models onto the accelerator at construction
time, which is expensive. DoclingExtractor is meant to be built exactly
once per process and reused for every file in the batch ("keep docling
hot") rather than re-instantiated per document.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Optional, Tuple

from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption
from docling_core.types.doc.document import DoclingDocument

from resume_pipeline.config import DoclingConfig

_DEVICE_MAP = {
    "cuda": AcceleratorDevice.CUDA,
    "mps": AcceleratorDevice.MPS,
    "cpu": AcceleratorDevice.CPU,
    "auto": AcceleratorDevice.AUTO,
}
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_OCR_FALLBACK_WORDS = 50


class DoclingExtractor:
    """Owns a single warm DocumentConverter for the lifetime of the process."""

    def __init__(self, config: DoclingConfig):
        device = _DEVICE_MAP.get(config.device.lower(), AcceleratorDevice.AUTO)

        self._device = device
        self._num_threads = config.num_threads
        self._do_ocr = config.do_ocr
        self._converter = self._build_converter(force_full_page_ocr=False)
        self._ocr_converter: Optional[DocumentConverter] = None

    def _build_converter(self, *, force_full_page_ocr: bool) -> DocumentConverter:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = AcceleratorOptions(
            num_threads=self._num_threads,
            device=self._device,
        )
        pipeline_options.do_ocr = self._do_ocr
        pipeline_options.ocr_options.force_full_page_ocr = force_full_page_ocr
        return DocumentConverter(
            format_options={
                "pdf": PdfFormatOption(pipeline_options=pipeline_options),
                "docx": WordFormatOption(),
            }
        )

    def convert(
        self, file_path: Path, document_json_path: Optional[Path] = None
    ) -> Tuple[str, DoclingDocument, bool]:
        """Convert and retry low-yield PDFs with full-page OCR."""
        result = self._converter.convert(str(file_path))
        document = result.document
        markdown = document.export_to_markdown()
        used_ocr_fallback = False
        if (
            self._do_ocr
            and file_path.suffix.lower() == ".pdf"
            and len(_WORD_RE.findall(markdown)) < _OCR_FALLBACK_WORDS
        ):
            if self._ocr_converter is None:
                self._ocr_converter = self._build_converter(force_full_page_ocr=True)
            result = self._ocr_converter.convert(str(file_path))
            document = result.document
            markdown = document.export_to_markdown()
            used_ocr_fallback = True

        if document_json_path is not None:
            document_json_path.parent.mkdir(parents=True, exist_ok=True)
            document.save_as_json(document_json_path)
            markdown_name = document_json_path.name.removesuffix(".docling.json") + ".md"
            document_json_path.with_name(markdown_name).write_text(markdown, encoding="utf-8")
        return markdown, document, used_ocr_fallback

    def to_markdown(
        self, file_path: Path, document_json_path: Optional[Path] = None
    ) -> Tuple[str, bool]:
        """Convert a PDF or DOCX file to markdown text. Raises on failure —
        callers are expected to wrap this in their own try/except."""
        markdown, _document, used_ocr_fallback = self.convert(file_path, document_json_path)
        return markdown, used_ocr_fallback
