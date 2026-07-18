# Parse Quality Report

Generated: 2026-07-18

## Evaluation Scope

This repository currently contains **one actual resume PDF** (`res2.pdf`) and four deliberately varied regression fixtures (`.txt`, `.xml`, unsupported, and empty input). The fixture results verify failure handling; they are **not presented as resumes from the organizer's Google Drive dataset**.

The full organizer Drive folder is not present in this workspace, so this report does not claim coverage of those files. Before judging the full dataset, run:

```bash
.venv/bin/python -m resume_pipeline.cli /path/to/downloaded/drive/folder
```

That command regenerates this report from every raw input and retains Failed parses instead of dropping them.

## Why Edge-Case Fixtures Are Included

This solution runs the actual AI pipeline for each PDF: Docling performs layout-aware document reconstruction and OCR when needed, Gemma extracts evidence-backed fields from the recovered document, and Qwen interprets ambiguous grade values before deterministic Python validation. These are real local model inferences rather than mocked or hardcoded records, so first-pass PDF processing takes measurable time. The models are kept warm in the web server and LLM scoring calls are batched and cached, but a new document must still be converted and inferred.

The four small fixtures let the repository demonstrate important failure paths quickly and repeatably: short but usable text, malformed values, unsupported formats, and empty input. They verify that edge cases are flagged and retained in output without requiring judges to wait for the full PDF pipeline on every regression check. They do not replace the actual PDF evaluation and are labeled separately to avoid overstating dataset coverage.

## Actual PDF Result

| File | Input Type | Method | Quality Flag | Words Recovered | Anomalies |
|---|---|---|---|---:|---:|
| res2.pdf | Real resume PDF | Docling layout extraction | Partial | 229 | 0 |

### What Was Successfully Recovered

- Identity: Ananya Subramanian, email, and phone
- Education: Anna University, B.E. Information Technology, graduation year 2022
- Skills: 14
- Projects: 2
- Experience entries: 2
- Certifications: 2
- Evidence provenance: 28 of 28 extracted evidence quotes located in the source PDF
- CGPA: correctly left `null` because no CGPA or percentage was found

### Why It Is Marked Partial

The extracted document ends with the meaningful year range `2018 - 2022`. The conservative truncation heuristic treats a short final line without punctuation as a possible cut-off and therefore assigns `Partial`. No field anomaly or extraction failure was detected. In practical terms, this PDF parsed successfully; the lower flag avoids overstating certainty when the heuristic cannot prove the final line is complete.

## Regression Fixtures

These inputs exist to demonstrate that malformed and unsupported files remain visible.

| File | Fixture Purpose | Method | Quality | Anomalies | Result |
|---|---|---|---|---:|---|
| sample1.txt | Short plain-text resume | text | Partial | 0 | Structured fields extracted; short-text flag |
| sample2.xml | Malformed-value sanity checks | xml | Partial | 2 | Bad email and out-of-range year surfaced |
| sample3.unsupported | Unsupported extension | unsupported | Failed | 1 | Explicit Failed Parse; no score |
| sample4_empty.txt | Empty input | text | Failed | 1 | Explicit Failed Parse; no score |

## Quality Definitions

- **Clean:** sufficient coherent text, no corruption/truncation signals.
- **Partial:** usable extraction with a short-text, truncation, or recoverable-quality concern.
- **Failed:** no usable text, unsupported input, or severe extraction corruption. The candidate remains in output and requires human review.

## OCR Status

The current actual PDF contains extractable text, so OCR fallback was not triggered. For a PDF yielding fewer than 50 words, the pipeline automatically retries with full-page OCR and reports the method as `docling+ocr`. No scanned organizer resume was available locally to claim an OCR result here.
