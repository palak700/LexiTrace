from __future__ import annotations


def estimate_ai_contribution(probabilities: dict[str, float], feature_hints: dict[str, float] | None = None) -> int:
    """Development approximation, not a validated authorship percentage."""
    feature_hints = feature_hints or {}
    ai_mass = (
        probabilities.get("ai_generated", 0.0)
        + probabilities.get("ai_polished_human", 0.0) * 0.85
        + probabilities.get("humanized_ai", 0.0) * 0.65
    )
    sentence_bonus = 0.05 if feature_hints.get("average_sentence_length", 0) > 22 else 0
    diversity_bonus = 0.04 if 0.35 <= feature_hints.get("vocabulary_diversity", 0) <= 0.55 else 0
    return max(0, min(100, round((ai_mass + sentence_bonus + diversity_bonus) * 100)))
