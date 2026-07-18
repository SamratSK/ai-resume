# AI Usage Log

Local Gemma 4 E4B is used for full-resume field extraction, skill-tier adjudication, project and experience assessment, conflict adjustment, explanation bullets, semantic chat answers, and parsing pasted job descriptions. Local Qwen3 0.6B interprets ambiguous grade text and routes chat/filter requests. Qwen3 Embedding 0.6B creates vectors for resume profile, project, and experience chunks stored in Chroma.

AI output is never accepted as a final score. Python validates model JSON, normalizes grades, applies configured weights, executes exact structured filters, enforces slot limits, assigns confidence from parse quality, and includes every failed parse. LLM calls use temperature zero and content-addressed caching for repeatability. I added defensive parsing, per-item fallbacks, evidence fields, deterministic arithmetic, provenance matching, OCR retry logic, and tests beyond model-generated responses.
