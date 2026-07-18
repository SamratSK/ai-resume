"""Scores every (resume, JD) pair, batching LLM calls across candidates at
every stage (skill tiers, project/experience score, holistic adjustment,
reasoning bullets) instead of issuing them one candidate at a time.

score_all() is the importable entry point a future FastAPI frontend calls
directly; score.py (the CLI) is a thin wrapper that also persists results
to disk via output_writer. score_one() scores a single candidate through
the exact same batched machinery (a batch of one), for on-demand use.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from resume_pipeline.model_client import LLMClient
from resume_pipeline.schema import ResumeRecord
from scoring import llm_judgment, reasoning, score_components, skill_matcher
from scoring.cache import DiskCache
from scoring.config import ScoringConfig
from scoring.confidence import compute_confidence
from scoring.jd_loader import JobDescription, load_jds
from scoring.resume_loader import load_resumes
from scoring.score_components import ComponentResult
from scoring.skill_matcher import SkillMatch


class ScoredCandidate(BaseModel):
    doc_id: str
    file: str
    parse_quality: str
    score: Optional[float] = None
    confidence: Optional[str] = None
    human_review_required: bool = False
    breakdown: Optional[Dict[str, ComponentResult]] = None
    required_skill_matches: List[SkillMatch] = []
    preferred_skill_matches: List[SkillMatch] = []
    reasoning_bullets: List[str] = []
    anomalies: List[str] = []
    error: Optional[str] = None  # set only if scoring this candidate raised unexpectedly


def score_jd(
    jd: JobDescription, records: List[Tuple[str, ResumeRecord]], llm_client: LLMClient, cache: DiskCache, config: ScoringConfig
) -> List[ScoredCandidate]:
    batch_size = config.model.batch_size
    output: List[ScoredCandidate] = []
    active: List[Tuple[str, ResumeRecord]] = []

    for doc_id, record in records:
        if record.parse_quality == "Failed":
            output.append(
                ScoredCandidate(doc_id=doc_id, file=record.file, parse_quality=record.parse_quality, human_review_required=True, anomalies=record.anomalies)
            )
        else:
            active.append((doc_id, record))

    if not active:
        return output

    record_by_id = {doc_id: record for doc_id, record in active}
    errored: Dict[str, str] = {}

    # Stage 1: skill matching (batched; per-candidate resilience already inside)
    try:
        skill_results = skill_matcher.resolve_skill_matches_for_candidates(jd, active, llm_client, cache, config.tier_credits, batch_size)
    except Exception as exc:
        skill_results = {}
        for doc_id, _ in active:
            errored[doc_id] = f"skill matching stage failed: {exc}"

    # Stage 2: mechanical (Python) scoring, per candidate
    mechanical: Dict[str, dict] = {}
    for doc_id, record in active:
        if doc_id in errored:
            continue
        try:
            required_matches, preferred_matches = skill_results[doc_id]
            mechanical[doc_id] = {
                "required_matches": required_matches,
                "preferred_matches": preferred_matches,
                "required_skills": score_components.required_skills_score(required_matches, config.weights.required_skills_points),
                "preferred_skills": score_components.preferred_skills_score(preferred_matches, config.weights.preferred_skills_points),
                "cgpa": score_components.cgpa_score(record.cgpa, jd.cgpa_min, config.weights.cgpa_points, config.cgpa.scale_window),
            }
        except Exception as exc:
            errored[doc_id] = f"mechanical scoring failed: {exc}"

    remaining = [(doc_id, record) for doc_id, record in active if doc_id not in errored]

    # Stage 3: projects/experience score (batched)
    try:
        projects_results = llm_judgment.assess_projects_experience_batch(
            jd, remaining, llm_client, cache, config.projects_rubric, config.weights.projects_experience_points, batch_size
        )
    except Exception as exc:
        projects_results = {}
        for doc_id, _ in remaining:
            errored[doc_id] = f"projects/experience scoring stage failed: {exc}"
    remaining = [(doc_id, record) for doc_id, record in remaining if doc_id not in errored]

    # Stage 4: partial breakdowns
    partial_breakdowns: Dict[str, Dict[str, ComponentResult]] = {}
    for doc_id, _record in remaining:
        m = mechanical[doc_id]
        partial_breakdowns[doc_id] = {
            "required_skills": m["required_skills"],
            "preferred_skills": m["preferred_skills"],
            "cgpa": m["cgpa"],
            "projects_experience": projects_results[doc_id],
        }

    # Stage 5: holistic adjustment (batched) — sees the breakdown so far
    adjustment_inputs = [
        (doc_id, record, {k: v.model_dump() for k, v in partial_breakdowns[doc_id].items()}) for doc_id, record in remaining
    ]
    try:
        adjustment_results = llm_judgment.holistic_adjustment_batch(
            jd, adjustment_inputs, llm_client, cache, config.weights.holistic_adjustment_max, batch_size
        )
    except Exception as exc:
        adjustment_results = {}
        for doc_id, _ in remaining:
            errored[doc_id] = f"holistic adjustment stage failed: {exc}"
    remaining = [(doc_id, record) for doc_id, record in remaining if doc_id not in errored]

    # Stage 6: final score + full breakdown
    full_breakdowns: Dict[str, Dict[str, ComponentResult]] = {}
    final_scores: Dict[str, float] = {}
    for doc_id, _record in remaining:
        partial = partial_breakdowns[doc_id]
        adjustment_result = adjustment_results[doc_id]
        raw_total = sum(c.points for c in partial.values()) + adjustment_result.points
        final_scores[doc_id] = round(max(0.0, min(raw_total, 100.0)), 2)
        full_breakdowns[doc_id] = {**partial, "holistic_adjustment": adjustment_result}

    # Stage 7: reasoning bullets (batched) — only after everything else is final
    bullet_inputs: List[Tuple[str, Dict[str, Any]]] = []
    for doc_id, _record in remaining:
        summary = {k: v.model_dump() for k, v in full_breakdowns[doc_id].items()}
        summary["final_score"] = final_scores[doc_id]
        bullet_inputs.append((doc_id, summary))
    try:
        bullets_results = reasoning.generate_reasoning_bullets_batch(jd.role, bullet_inputs, llm_client, cache, batch_size)
    except Exception as exc:
        bullets_results = {doc_id: [f"Reasoning bullets unavailable: {exc}"] for doc_id, _ in remaining}

    # Stage 8: confidence + assemble
    for doc_id, record in remaining:
        m = mechanical[doc_id]
        confidence_result = compute_confidence(record, m["required_matches"] + m["preferred_matches"])
        output.append(
            ScoredCandidate(
                doc_id=doc_id,
                file=record.file,
                parse_quality=record.parse_quality,
                score=final_scores[doc_id],
                confidence=confidence_result.confidence,
                human_review_required=confidence_result.human_review_required,
                breakdown=full_breakdowns[doc_id],
                required_skill_matches=m["required_matches"],
                preferred_skill_matches=m["preferred_matches"],
                reasoning_bullets=bullets_results.get(doc_id, []),
                anomalies=record.anomalies,
            )
        )

    for doc_id, reason in errored.items():
        record = record_by_id[doc_id]
        output.append(
            ScoredCandidate(
                doc_id=doc_id, file=record.file, parse_quality=record.parse_quality, human_review_required=True, anomalies=record.anomalies, error=reason
            )
        )

    return output


def score_one(doc_id: str, record: ResumeRecord, jd: JobDescription, llm_client: LLMClient, cache: DiskCache, config: ScoringConfig) -> ScoredCandidate:
    """Scores a single resume against a single JD through the exact same
    batched machinery as score_all (batch of one) — for a frontend scoring
    one newly-uploaded resume on demand."""
    return score_jd(jd, [(doc_id, record)], llm_client, cache, config)[0]


def score_all(config: ScoringConfig) -> Dict[str, List[ScoredCandidate]]:
    """Scores every resume in config.paths.resumes_dir against every JD in
    config.paths.jds_dir. Returns {jd_id: [ScoredCandidate, ...]}."""
    jds = load_jds(config.paths.jds_dir)
    records, load_errors = load_resumes(config.paths.resumes_dir)

    llm_client = LLMClient(config.model)
    cache = DiskCache(config.paths.cache_dir)

    results: Dict[str, List[ScoredCandidate]] = {}
    try:
        for jd in jds:
            try:
                candidates = score_jd(jd, records, llm_client, cache, config)
            except Exception as exc:  # one bad JD never kills the rest of the run
                candidates = [
                    ScoredCandidate(doc_id=doc_id, file=record.file, parse_quality=record.parse_quality, human_review_required=True, anomalies=record.anomalies, error=str(exc))
                    for doc_id, record in records
                ]
            for load_error in load_errors:
                candidates.append(
                    ScoredCandidate(
                        doc_id=load_error.file_name,
                        file=load_error.file_name,
                        parse_quality="Failed",
                        human_review_required=True,
                        anomalies=[f"load_failed:{load_error.reason}"],
                        error=load_error.reason,
                    )
                )
            results[jd.id] = candidates
    finally:
        llm_client.close()

    return results
