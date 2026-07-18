# Design Decisions

## Tricky Part 1: PDF Layout Chaos

PDF and DOCX files go through Docling because its layout model reconstructs reading order from page geometry instead of concatenating raw PDF text coordinates. The complete DoclingDocument is retained for auditability. This handles common two-column, table, and floating-text layouts better than a plain text extractor. It can still misorder heavily graphical Canva templates or text rendered as icons; those cases are surfaced through parse-quality checks and field evidence rather than silently trusted.

## Tricky Part 2: The Scanned Resume

The first Docling pass uses automatic OCR. If a PDF still yields fewer than 50 words, the parser detects the low yield and retries with full-page OCR enabled. The report marks that method as `docling+ocr`. The OCR result passes through the same quality checks, so unreadable scans remain Partial or Failed with a reason. Known limits are low resolution, handwriting, rotated pages, and highly decorative backgrounds.

## Tricky Part 3: Skills in Unstructured Text

Gemma receives the complete reconstructed resume, not only a section named Skills, and extracts technologies found in projects, experience, courses, and prose with verbatim evidence. Stage 2 then combines deterministic normalization and synonym matching with batched LLM adjudication for partial or implicit matches. This may miss skills represented only by logos or infer a broad concept too aggressively; implicit and partial matches therefore receive reduced credit and are flagged.

## Tricky Part 4: Parse Quality and Score Confidence

Parse quality and field confidence remain separate. Clean records can be High unless low-confidence fields or anomalies reduce them; Partial records are capped below High; Failed records receive no score, are placed in Excluded, and require human review. A strong score from incomplete text can therefore remain visible but cannot claim high certainty. The shortlist always includes failed records so missing evidence is explicit.
