"""Format router: picks the right text-extraction path per file extension.

Every path either returns (text, method) or raises ParseFailure — there is
no silent-skip branch. Callers (pipeline.py) catch ParseFailure and record
it in the report as a Failed Parse.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from bs4 import BeautifulSoup

from resume_pipeline.docling_wrapper import DoclingExtractor

_DOCLING_SUFFIXES = {".pdf", ".docx"}


class ParseFailure(Exception):
    """Raised whenever a file cannot be turned into usable text.

    `method` records what was attempted (docling/text/xml/unsupported) so
    the report can show *how* a file failed, not just that it did.
    """

    def __init__(self, method: str, reason: str):
        super().__init__(reason)
        self.method = method
        self.reason = reason


def extract_text(
    file_path: Path,
    docling_extractor: DoclingExtractor,
    document_json_path: Optional[Path] = None,
) -> Tuple[str, str]:
    suffix = file_path.suffix.lower()

    if suffix in _DOCLING_SUFFIXES:
        method = "docling"
        try:
            text, used_ocr_fallback = docling_extractor.to_markdown(file_path, document_json_path)
            if used_ocr_fallback:
                method = "docling+ocr"
        except Exception as exc:  # docling can raise a wide variety of errors
            raise ParseFailure(method, f"docling conversion failed: {exc}") from exc
    elif suffix == ".txt":
        method = "text"
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ParseFailure(method, f"failed to read text file: {exc}") from exc
    elif suffix == ".xml":
        method = "xml"
        try:
            text = _extract_xml_text(file_path)
        except Exception as exc:
            raise ParseFailure(method, f"failed to parse xml: {exc}") from exc
    else:
        raise ParseFailure("unsupported", f"unsupported file extension: {suffix or '(none)'}")

    if not text or not text.strip():
        raise ParseFailure(method, "extracted text is empty")

    return text, method


def _extract_xml_text(file_path: Path) -> str:
    raw = file_path.read_bytes()
    soup = BeautifulSoup(raw, "xml")  # bs4 uses lxml as the xml parser backend
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
