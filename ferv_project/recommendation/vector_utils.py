"""
vector_utils.py
---------------
Pure-Python vector helpers for the recommendation pipelines.
No numpy dependency. Functions are side-effect free; the RNG is injectable
so callers (and tests) can pin determinism.
"""

import math
import random
from typing import Hashable, Sequence


def random_unit_vector(dim: int, rng: random.Random | None = None) -> list[float]:
    """
    Sample a uniformly-random unit vector in R^dim using the Gaussian trick:
    isotropic Gaussian samples normalized to length 1.
    """
    if dim <= 0:
        raise ValueError(f"dim must be positive, got {dim}")
    r = rng if rng is not None else random
    v = [r.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in v))
    if norm == 0.0:
        # Astronomically unlikely; resample once with a fresh draw.
        return random_unit_vector(dim, rng)
    return [x / norm for x in v]


def vector_add_scaled(
    base: list[float], direction: list[float], scalar: float
) -> list[float]:
    """Return base + scalar * direction. Raises if lengths differ."""
    if len(base) != len(direction):
        raise ValueError(
            f"length mismatch: base={len(base)}, direction={len(direction)}"
        )
    return [b + scalar * d for b, d in zip(base, direction)]


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[Hashable]], c: int = 60
) -> list[tuple[Hashable, float]]:
    """
    Reciprocal Rank Fusion across n ranked lists of opaque IDs.

    For each list, an item at zero-based rank r contributes 1 / (c + r + 1)
    to its total score. The +1 makes the first item contribute 1/(c+1) — the
    standard Cormack/Buettcher/Clarke formulation — and the +1 inside guards
    against c=0 collapsing the top item to a divide-by-zero.

    Returns (id, score) pairs sorted by score descending. Ties are broken by
    earliest first-appearance across the input lists, then by lexicographic
    order on the id, so the output is deterministic.

    Empty input → []. Lists may overlap, may be empty, and may have different
    lengths. Items repeated within a single list count only at their first
    occurrence in that list.
    """
    if c < 0:
        raise ValueError(f"c must be non-negative, got {c}")

    scores: dict[Hashable, float] = {}
    first_seen: dict[Hashable, int] = {}
    seq = 0
    for ranked in ranked_lists:
        seen_in_list: set[Hashable] = set()
        for rank, item in enumerate(ranked):
            if item in seen_in_list:
                continue
            seen_in_list.add(item)
            scores[item] = scores.get(item, 0.0) + 1.0 / (c + rank + 1)
            if item not in first_seen:
                first_seen[item] = seq
                seq += 1

    return sorted(
        scores.items(),
        key=lambda kv: (-kv[1], first_seen[kv[0]], str(kv[0])),
    )
