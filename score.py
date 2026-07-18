"""CLI: python score.py --resumes extracted/ --jds jds/ --out output/

Scoring itself is also directly importable — see scoring.scorer.score_all —
so a future FastAPI frontend can call it without going through this CLI.
"""
from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path
from typing import List, Optional

from scoring.config import load_scoring_config
from scoring.jd_loader import load_jds
from scoring.output_writer import write_jd_outputs, write_summary_md
from scoring.scorer import score_all
from scoring.shortlist import build_shortlist


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 2 resume scoring & shortlisting engine")
    parser.add_argument("--resumes", type=Path, required=True, help="Folder of Stage 1 extracted/<resume>.json files")
    parser.add_argument("--jds", type=Path, required=True, help="Folder of JD JSON files")
    parser.add_argument("--out", type=Path, required=True, help="Output folder for shortlists + summary")
    parser.add_argument("--config", type=Path, default=None, help="Path to scoring_config.yaml (default: repo root)")
    args = parser.parse_args(argv)

    config = load_scoring_config(args.config)
    config = dataclasses.replace(
        config,
        paths=dataclasses.replace(
            config.paths,
            resumes_dir=args.resumes.resolve(),
            jds_dir=args.jds.resolve(),
            output_dir=args.out.resolve(),
        ),
    )

    results = score_all(config)
    jd_by_id = {jd.id: jd for jd in load_jds(config.paths.jds_dir)}

    summary_lines = []
    for jd_id, candidates in results.items():
        jd = jd_by_id[jd_id]
        shortlist_result = build_shortlist(jd, candidates, config.shortlist.score_cutoff)
        summary_line = write_jd_outputs(shortlist_result, config.paths.output_dir)
        summary_lines.append(summary_line)
        print(
            f"{jd.id}: evaluated={summary_line.candidates_evaluated} "
            f"shortlisted={summary_line.shortlisted} cutoff={summary_line.cutoff} "
            f"parse_failures={summary_line.parse_failures}"
        )

    write_summary_md(summary_lines, config.paths.output_dir)
    print(f"\nOutputs written to {config.paths.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
