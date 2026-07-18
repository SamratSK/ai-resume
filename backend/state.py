"""Process-wide singletons: the warm Docling converter and the LLM clients,
built once at app startup and reused across every request. This is what
"keep docling hot" means in a server: unlike the CLI (which pays the model
load cost per invocation), the server pays it once and stays warm for the
life of the process.
"""
from __future__ import annotations

from pathlib import Path

from resume_pipeline.config import PipelineConfig, load_config
from resume_pipeline.docling_wrapper import DoclingExtractor
from resume_pipeline.model_client import LLMClient
from scoring.cache import DiskCache
from scoring.config import ScoringConfig, load_scoring_config
from backend.rag import HybridChatService

REPO_ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = REPO_ROOT / "uploads"

stage1_config: PipelineConfig = load_config()
scoring_config: ScoringConfig = load_scoring_config()

docling_extractor: DoclingExtractor
extraction_llm: LLMClient
interpretation_llm: LLMClient
scoring_llm: LLMClient
scoring_cache: DiskCache
chat_service: HybridChatService


def init_singletons() -> None:
    global docling_extractor, extraction_llm, interpretation_llm, scoring_llm, scoring_cache, chat_service
    docling_extractor = DoclingExtractor(stage1_config.docling)
    extraction_llm = LLMClient(stage1_config.extraction)
    interpretation_llm = LLMClient(stage1_config.interpretation)
    scoring_llm = LLMClient(scoring_config.model)
    scoring_cache = DiskCache(scoring_config.paths.cache_dir)
    chat_service = HybridChatService(REPO_ROOT)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    stage1_config.paths.output_dir.mkdir(parents=True, exist_ok=True)
    scoring_config.paths.jds_dir.mkdir(parents=True, exist_ok=True)
    scoring_config.paths.output_dir.mkdir(parents=True, exist_ok=True)


def shutdown_singletons() -> None:
    extraction_llm.close()
    interpretation_llm.close()
    scoring_llm.close()
    chat_service.close()
