"""Runs the Stage 2 scorer three times, as three separate processes, against
the same inputs and diffs the outputs programmatically.

Every LLM call is cached to disk by content hash (on top of temperature 0),
so runs 2 and 3 should never call the model at all — they just replay run
1's cache. All three outputs must therefore be byte-identical.

Usage: uv run python stability_test.py [--resumes extracted] [--jds jds]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent


def run_scoring(resumes: Path, jds: Path, out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "score.py"), "--resumes", str(resumes), "--jds", str(jds), "--out", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"scoring run against {out_dir} failed (exit {result.returncode})")


def diff_dirs(a: Path, b: Path) -> List[str]:
    diffs = []
    a_files = sorted(p.name for p in a.glob("*") if p.is_file())
    b_files = sorted(p.name for p in b.glob("*") if p.is_file())
    if a_files != b_files:
        diffs.append(f"file lists differ: {a_files} vs {b_files}")
        return diffs
    for name in a_files:
        content_a = (a / name).read_text(encoding="utf-8")
        content_b = (b / name).read_text(encoding="utf-8")
        if content_a != content_b:
            diffs.append(f"{name} differs between {a.name} and {b.name}")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 2 scoring 3x and verify byte-identical output")
    parser.add_argument("--resumes", type=Path, default=REPO_ROOT / "extracted")
    parser.add_argument("--jds", type=Path, default=REPO_ROOT / "jds")
    parser.add_argument("--work-dir", type=Path, default=REPO_ROOT / ".stability_test_runs")
    args = parser.parse_args()

    args.work_dir.mkdir(parents=True, exist_ok=True)
    run_dirs = [args.work_dir / f"run{i}" for i in (1, 2, 3)]

    for i, run_dir in enumerate(run_dirs, start=1):
        print(f"Run {i}/3 -> {run_dir}")
        run_scoring(args.resumes, args.jds, run_dir)

    all_diffs = diff_dirs(run_dirs[0], run_dirs[1]) + diff_dirs(run_dirs[1], run_dirs[2])

    if all_diffs:
        print("\nSTABILITY TEST FAILED — differences found:")
        for d in all_diffs:
            print(f"  - {d}")
        return 1

    print("\nSTABILITY TEST PASSED — all 3 runs produced byte-identical output.")
    shutil.rmtree(args.work_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
