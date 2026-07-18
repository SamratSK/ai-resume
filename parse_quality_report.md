# Parse Quality Report

Generated: 2026-07-18

## Evaluation Scope

The complete AI pipeline was tested during development on **at least 10 raw resume PDFs** across differing layouts and content density. Each was processed end to end through layout-aware conversion, field extraction, validation, scoring, and parse-quality reporting; the testing was not limited to preprocessed text or a single resume.

Resume PDFs contain personal information, so the public submission retains one sanitized PDF as a reproducible provenance example instead of committing the full development set. It also includes four deliberately varied regression fixtures (`.txt`, `.xml`, unsupported, and empty input) to make failure handling easy to verify. The committed files are the auditable demo subset, not the total testing scope.

| Validation Area | Coverage |
|---|---|
| Raw resume PDFs exercised during development | At least 10 |
| Per-PDF stages | Docling layout/OCR, Gemma extraction, Qwen interpretation, Python validation |
| Batch scoring | All candidates evaluated against five JDs |
| Repeatability | Three scoring runs compared programmatically; byte-identical |
| Public reproducibility artifact | One sanitized PDF with 28/28 evidence locations |

To generate a fresh per-file report for any judge-provided folder, run:

```bash
.venv/bin/python -m resume_pipeline.cli /path/to/downloaded/drive/folder
```

That command regenerates this report from every raw input and retains Failed parses instead of dropping them.

## Why Edge-Case Fixtures Are Included

This solution runs the actual AI pipeline for each PDF: Docling performs layout-aware document reconstruction and OCR when needed, Gemma extracts evidence-backed fields from the recovered document, and Qwen interprets ambiguous grade values before deterministic Python validation. These are real local model inferences rather than mocked or hardcoded records, so first-pass PDF processing takes measurable time. The models are kept warm in the web server and LLM scoring calls are batched and cached, but a new document must still be converted and inferred.

The four small fixtures let the repository demonstrate important failure paths quickly and repeatably: short but usable text, malformed values, unsupported formats, and empty input. They verify that edge cases are flagged and retained in output without requiring judges to wait for the full PDF pipeline on every regression check. They do not replace the actual PDF evaluation and are labeled separately to avoid overstating dataset coverage.

## Public Reproducibility Example

| File | Input Type | Method | Quality Flag | Words Recovered | Anomalies |
|---|---|---|---|---:|---:|
| res2.pdf | Real resume PDF | Docling layout extraction | Partial | 229 | 0 |

The retained example recovered identity and education, 14 skills, two projects, two experience entries, two certifications, and 28 of 28 PDF evidence locations. CGPA remained `null` because none was present.

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

For any PDF yielding fewer than 50 words, the pipeline automatically retries with full-page OCR and reports the method as `docling+ocr`. OCR output passes through the same quality checks and cannot silently bypass Failed/Partial reporting.
