from __future__ import annotations

from enum import Enum


class DifficultyTier(str, Enum):
    """Mechanically controlled cognitive-v2 difficulty strata."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


DIFFICULTY_TIERS = (
    DifficultyTier.EASY,
    DifficultyTier.MEDIUM,
    DifficultyTier.HARD,
)


def difficulty_for_variant(variant: int) -> DifficultyTier:
    if variant < 0:
        raise ValueError("variant must be non-negative")
    return DIFFICULTY_TIERS[variant % len(DIFFICULTY_TIERS)]
