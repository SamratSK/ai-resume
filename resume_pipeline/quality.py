"""Parse-quality heuristics: Clean / Partial / Failed, judged purely from
the extracted text (no LLM call). This is a separate axis from field-level
confidence produced later by the extraction model — never merge the two.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List

MIN_CHARS_NEAR_EMPTY = 40
MIN_WORDS_CLEAN = 80
MAX_TOKEN_REPEAT_RATIO = 0.30
MAX_NGRAM_REPEAT_RUN = 6
MIN_ALPHA_RATIO = 0.35
MIN_UNIQUE_TOKEN_RATIO = 0.15

_WORD_RE = re.compile(r"[A-Za-z]{2,}")


@dataclass
class QualityAssessment:
    quality: str  # "Clean" | "Partial" | "Failed"
    reasons: List[str] = field(default_factory=list)


def assess_parse_quality(text: str) -> QualityAssessment:
    stripped = text.strip()

    if len(stripped) < MIN_CHARS_NEAR_EMPTY:
        return QualityAssessment("Failed", ["near_empty_text"])

    reasons: List[str] = []
    tokens = stripped.split()

    alpha_chars = sum(1 for c in stripped if c.isalpha())
    non_space_chars = sum(1 for c in stripped if not c.isspace())
    alpha_ratio = alpha_chars / non_space_chars if non_space_chars else 0.0
    if alpha_ratio < MIN_ALPHA_RATIO:
        reasons.append("low_alphabetic_ratio")

    if tokens:
        counts = Counter(t.lower() for t in tokens)
        top_token, top_count = counts.most_common(1)[0]
        if len(tokens) >= 20 and top_count / len(tokens) > MAX_TOKEN_REPEAT_RATIO:
            reasons.append(f"looping_token:{top_token!r}")

        unique_ratio = len(counts) / len(tokens)
        if len(tokens) >= 40 and unique_ratio < MIN_UNIQUE_TOKEN_RATIO:
            reasons.append("low_token_diversity")

    if _has_repeated_ngram_run(tokens):
        reasons.append("repeated_ngram_sequence")

    if reasons:
        return QualityAssessment("Failed", reasons)

    word_count = len(_WORD_RE.findall(stripped))
    if word_count < MIN_WORDS_CLEAN:
        return QualityAssessment("Partial", ["short_text"])

    if _looks_truncated(stripped):
        return QualityAssessment("Partial", ["truncated_ending"])

    return QualityAssessment("Clean", [])


def _has_repeated_ngram_run(tokens: List[str], n: int = 3, max_repeats: int = MAX_NGRAM_REPEAT_RUN) -> bool:
    if len(tokens) < n * max_repeats:
        return False
    lowered = [t.lower() for t in tokens]
    ngrams = [tuple(lowered[i : i + n]) for i in range(len(lowered) - n + 1)]
    run = 1
    for i in range(1, len(ngrams)):
        if ngrams[i] == ngrams[i - 1]:
            run += 1
            if run >= max_repeats:
                return True
        else:
            run = 1
    return False


def _looks_truncated(text: str) -> bool:
    lines = text.splitlines()
    if not lines:
        return False
    last_line = lines[-1].strip()
    if not last_line:
        return False
    ends_clean = last_line.endswith((".", ":", ")", "%", "!", "?"))
    return len(last_line) < 40 and not ends_clean and last_line[-1].isalnum()
