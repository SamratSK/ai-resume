"""Loads config.yaml once and exposes typed access to it.

Every module that needs a model endpoint or a path pulls it from here —
nothing is hardcoded downstream so the whole pipeline is reconfigurable
from one file.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass(frozen=True)
class DoclingConfig:
    device: str
    num_threads: int
    do_ocr: bool


@dataclass(frozen=True)
class ModelEndpointConfig:
    base_url: str
    model: str
    timeout_seconds: float
    max_retries: int
    temperature: float
    batch_size: int = 1


@dataclass(frozen=True)
class PathsConfig:
    output_dir: Path
    report_path: Path


@dataclass(frozen=True)
class PipelineConfig:
    docling: DoclingConfig
    extraction: ModelEndpointConfig
    interpretation: ModelEndpointConfig
    paths: PathsConfig
    interpret_fields: List[str]


def load_config(config_path: Path | str | None = None) -> PipelineConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    docling_raw = raw["docling"]
    models_raw = raw["models"]
    paths_raw = raw["paths"]
    base_dir = path.resolve().parent

    return PipelineConfig(
        docling=DoclingConfig(
            device=docling_raw["device"],
            num_threads=int(docling_raw.get("num_threads", 4)),
            do_ocr=bool(docling_raw.get("do_ocr", True)),
        ),
        extraction=ModelEndpointConfig(
            base_url=models_raw["extraction"]["base_url"],
            model=models_raw["extraction"]["model"],
            timeout_seconds=float(models_raw["extraction"].get("timeout_seconds", 120)),
            max_retries=int(models_raw["extraction"].get("max_retries", 1)),
            temperature=float(models_raw["extraction"].get("temperature", 0.0)),
        ),
        interpretation=ModelEndpointConfig(
            base_url=models_raw["interpretation"]["base_url"],
            model=models_raw["interpretation"]["model"],
            timeout_seconds=float(models_raw["interpretation"].get("timeout_seconds", 60)),
            max_retries=int(models_raw["interpretation"].get("max_retries", 1)),
            temperature=float(models_raw["interpretation"].get("temperature", 0.0)),
            batch_size=int(models_raw["interpretation"].get("batch_size", 20)),
        ),
        paths=PathsConfig(
            output_dir=(base_dir / paths_raw["output_dir"]).resolve(),
            report_path=(base_dir / paths_raw["report_path"]).resolve(),
        ),
        interpret_fields=list(raw.get("interpret_fields", [])),
    )
