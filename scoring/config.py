"""Loads scoring_config.yaml once. Every weight, rubric bound, and cutoff
used by the scoring engine is read from here — see that file for the single
source of truth on tunable numbers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from resume_pipeline.config import ModelEndpointConfig

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "scoring_config.yaml"


@dataclass(frozen=True)
class TierCredits:
    exact: float
    synonym: float
    partial: float
    implicit: float
    missing: float

    def get(self, tier: str) -> float:
        return getattr(self, tier)


@dataclass(frozen=True)
class Weights:
    required_skills_points: float
    preferred_skills_points: float
    cgpa_points: float
    projects_experience_points: float
    holistic_adjustment_max: float


@dataclass(frozen=True)
class CgpaConfig:
    scale_window: float


@dataclass(frozen=True)
class ProjectsRubric:
    relevance_max: int
    depth_max: int
    breadth_max: int
    total_max: int


@dataclass(frozen=True)
class ShortlistConfig:
    score_cutoff: float


@dataclass(frozen=True)
class ScoringPaths:
    resumes_dir: Path
    jds_dir: Path
    output_dir: Path
    cache_dir: Path


@dataclass(frozen=True)
class ScoringConfig:
    model: ModelEndpointConfig
    weights: Weights
    tier_credits: TierCredits
    cgpa: CgpaConfig
    projects_rubric: ProjectsRubric
    shortlist: ShortlistConfig
    paths: ScoringPaths


def load_scoring_config(config_path: Path | str | None = None) -> ScoringConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    base_dir = path.resolve().parent
    model_raw = raw["model"]
    weights_raw = raw["weights"]
    tiers_raw = raw["tier_credits"]
    cgpa_raw = raw["cgpa"]
    rubric_raw = raw["projects_experience_rubric"]
    shortlist_raw = raw["shortlist"]
    paths_raw = raw["paths"]

    return ScoringConfig(
        model=ModelEndpointConfig(
            base_url=model_raw["base_url"],
            model=model_raw["model"],
            timeout_seconds=float(model_raw.get("timeout_seconds", 120)),
            max_retries=int(model_raw.get("max_retries", 1)),
            temperature=float(model_raw.get("temperature", 0.0)),
            batch_size=int(model_raw.get("batch_size", 10)),
        ),
        weights=Weights(
            required_skills_points=float(weights_raw["required_skills_points"]),
            preferred_skills_points=float(weights_raw["preferred_skills_points"]),
            cgpa_points=float(weights_raw["cgpa_points"]),
            projects_experience_points=float(weights_raw["projects_experience_points"]),
            holistic_adjustment_max=float(weights_raw["holistic_adjustment_max"]),
        ),
        tier_credits=TierCredits(
            exact=float(tiers_raw["exact"]),
            synonym=float(tiers_raw["synonym"]),
            partial=float(tiers_raw["partial"]),
            implicit=float(tiers_raw["implicit"]),
            missing=float(tiers_raw["missing"]),
        ),
        cgpa=CgpaConfig(scale_window=float(cgpa_raw["scale_window"])),
        projects_rubric=ProjectsRubric(
            relevance_max=int(rubric_raw["relevance_max"]),
            depth_max=int(rubric_raw["depth_max"]),
            breadth_max=int(rubric_raw["breadth_max"]),
            total_max=int(rubric_raw["total_max"]),
        ),
        shortlist=ShortlistConfig(score_cutoff=float(shortlist_raw["score_cutoff"])),
        paths=ScoringPaths(
            resumes_dir=(base_dir / paths_raw["resumes_dir"]).resolve(),
            jds_dir=(base_dir / paths_raw["jds_dir"]).resolve(),
            output_dir=(base_dir / paths_raw["output_dir"]).resolve(),
            cache_dir=(base_dir / paths_raw["cache_dir"]).resolve(),
        ),
    )
