# InternLoom Submission Deliverables

## Required

| Deliverable | Path |
|---|---|
| Setup, run procedure, working example, differentiation | `README.md` |
| Pinned Python dependencies | `requirements.txt` |
| Sample shortlist outputs for all five JDs | `output/` |
| Parse quality report with actual-PDF scope | `parse_quality_report.md` |
| AI Usage Log | `AI_USAGE_LOG.md` |
| Four Tricky Parts design decisions | `DESIGN_DECISIONS.md` |
| Five supplied job descriptions | `jds/` |
| Stage 1 extraction engine | `resume_pipeline/` |
| Stage 2 scoring engine | `scoring/` and `score.py` |

## Bonus

| Bonus | Implementation |
|---|---|
| Web interface and CSV | `backend/`, `frontend/` |
| OCR fallback | `resume_pipeline/docling_wrapper.py` |
| Live unstructured JD parsing | `backend/jd_parser.py`, Jobs page Paste JD flow |
| Three-run score stability | `stability_test.py` |

## Additional Demonstration Material

| Material | Path |
|---|---|
| Combined outputs and screenshots PDF | `docs/InternLoom_Submission_Outputs.pdf` |
| Seven interface screenshots | `docs/screenshots/` |
| Extracted JSON and PDF provenance sample | `extracted/` |
| Raw regression inputs | `samples/` |
| Automated tests | `tests/`, `frontend/e2e/` |
| Reproducible screenshot/PDF scripts | `frontend/scripts/` |

## Submission Archive

`docs/InternLoom_Submission_Package.zip` contains the complete judge-facing repository snapshot without local models, virtual environments, caches, uploads, build output, or confidential `prob.pdf`.
