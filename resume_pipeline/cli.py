"""CLI: process every supported file in a folder into extracted/*.json plus
a parse_quality_report.md.

    uv run python -m resume_pipeline.cli /path/to/resumes
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from resume_pipeline.config import load_config
from resume_pipeline.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 1 resume extraction pipeline")
    parser.add_argument("folder", type=Path, help="Folder containing resume files to process")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.yaml (default: repo root)")
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"error: {args.folder} is not a directory", file=sys.stderr)
        return 1

    config = load_config(args.config)
    rows = run_pipeline(args.folder, config)

    counts = Counter(row.parse_quality for row in rows)
    print(f"Processed {len(rows)} file(s): "
          f"Clean={counts.get('Clean', 0)} Partial={counts.get('Partial', 0)} Failed={counts.get('Failed', 0)}")
    print(f"Extracted JSON -> {config.paths.output_dir}")
    print(f"Report -> {config.paths.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
