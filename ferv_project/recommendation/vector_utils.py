"""
vector_utils.py
---------------
Pure-Python vector helpers for the exploratory recommendation pipeline.
No numpy dependency. Functions are side-effect free; the RNG is injectable
so callers (and tests) can pin determinism.
"""

import math
import random


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
