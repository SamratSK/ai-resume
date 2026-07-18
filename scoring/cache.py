"""Content-hash-keyed disk cache for LLM results.

Every LLM call in Stage 2 (tier classification, project/experience scoring,
holistic adjustment) goes through here. The cache key is a hash of the
actual inputs to that call (not just doc_id/jd_id), so it self-invalidates
if a resume or JD changes, and — combined with temperature 0 — makes three
consecutive runs against the same inputs bit-identical: the 2nd and 3rd
runs never call the model at all, they just replay what's on disk.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List


class DiskCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, namespace: str, key_parts: List[Any]) -> Any:
        path = self._path_for(namespace, key_parts)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def put(self, namespace: str, key_parts: List[Any], value: Dict) -> None:
        path = self._path_for(namespace, key_parts)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=True)
        tmp_path.replace(path)  # atomic-ish: avoid a half-written cache entry

    def get_or_compute(self, namespace: str, key_parts: List[Any], compute_fn: Callable[[], Dict]) -> Dict:
        cached = self.get(namespace, key_parts)
        if cached is not None:
            return cached
        result = compute_fn()
        self.put(namespace, key_parts, result)
        return result

    def _path_for(self, namespace: str, key_parts: List[Any]) -> Path:
        digest = _content_hash(key_parts)
        return self.cache_dir / f"{namespace}__{digest}.json"


def _content_hash(key_parts: List[Any]) -> str:
    hasher = hashlib.sha256()
    for part in key_parts:
        hasher.update(json.dumps(part, sort_keys=True, default=str).encode("utf-8"))
        hasher.update(b"\x00")
    return hasher.hexdigest()[:32]
