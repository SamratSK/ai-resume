"""Generic cache-then-batch resolution, shared by skill_matcher,
llm_judgment, and reasoning.

Each item's cache entry is checked individually first — only cache MISSES
get grouped into chunks of at most batch_size and sent to the LLM together.
This means batching the wire calls never coarsens the cache: a candidate
scored alone yesterday and one scored today as part of a batch of 10 land
in the exact same cache entry, so either order of operations hits.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from scoring.cache import DiskCache

# (doc_id, payload passed to resolve_chunk_fn, cache key_parts)
Item = Tuple[str, Any, List[Any]]


def resolve_batched(
    namespace: str,
    items: List[Item],
    cache: DiskCache,
    batch_size: int,
    resolve_chunk_fn: Callable[[List[Item]], Dict[str, Any]],
) -> Dict[str, Any]:
    """resolve_chunk_fn receives a chunk of items (cache misses only) and
    must return {doc_id: result} covering every doc_id in that chunk."""
    results: Dict[str, Any] = {}
    pending: List[Item] = []

    for doc_id, payload, key_parts in items:
        cached = cache.get(namespace, key_parts)
        if cached is not None:
            results[doc_id] = cached
        else:
            pending.append((doc_id, payload, key_parts))

    step = max(batch_size, 1)
    for start in range(0, len(pending), step):
        chunk = pending[start : start + step]
        chunk_results = resolve_chunk_fn(chunk)
        for doc_id, _, key_parts in chunk:
            result = chunk_results[doc_id]
            cache.put(namespace, key_parts, result)
            results[doc_id] = result

    return results
