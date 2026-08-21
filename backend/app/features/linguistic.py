from __future__ import annotations

import math
import re
import statistics
from collections import Counter


WORD_RE = re.compile(r"\b[\w'-]+\b")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
PASSIVE_RE = re.compile(r"\b(am|is|are|was|were|be|been|being)\s+\w+(ed|en)\b", re.IGNORECASE)


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in SENTENCE_RE.findall(text) if sentence.strip()]


def _flesch_reading_ease(words: list[str], sentences: list[str]) -> float | None:
    if not words or not sentences:
        return None
    syllables = sum(max(1, len(re.findall(r"[aeiouy]+", word))) for word in words)
    score = 206.835 - (1.015 * (len(words) / len(sentences))) - (84.6 * (syllables / len(words)))
    return round(max(0, min(100, score)), 2)


def _pos_distribution(words: list[str]) -> dict[str, float]:
    if not words:
        return {}
    buckets: Counter[str] = Counter()
    for word in words:
        if word.endswith(("ly",)):
            buckets["adverb"] += 1
        elif word.endswith(("ing", "ed", "ize", "ise")):
            buckets["verb"] += 1
        elif word.endswith(("ous", "ful", "able", "ive", "al", "ic")):
            buckets["adjective"] += 1
        elif word in {"the", "a", "an"}:
            buckets["determiner"] += 1
        elif word in {"and", "but", "or", "because", "while", "although"}:
            buckets["conjunction"] += 1
        elif word in {"i", "you", "he", "she", "they", "we", "it"}:
            buckets["pronoun"] += 1
        else:
            buckets["noun_other"] += 1
    return {key: round(value / len(words), 3) for key, value in buckets.items()}


def analyze_linguistic_features(text: str) -> dict:
    words = _words(text)
    sentences = _sentences(text)
    sentence_lengths = [len(_words(sentence)) for sentence in sentences if _words(sentence)]

    if len(words) < 3:
        return {
            "perplexity": None,
            "vocabulary_diversity": None,
            "average_sentence_length": None,
            "burstiness": None,
            "readability": None,
            "passive_voice": None,
            "pos_distribution": {},
            "punctuation": dict(Counter(ch for ch in text if ch in ".,;:!?()[]{}\"'")),
        }

    vocabulary_diversity = len(set(words)) / len(words)
    average_sentence_length = statistics.mean(sentence_lengths) if sentence_lengths else None
    burstiness = (
        statistics.pstdev(sentence_lengths) / average_sentence_length
        if average_sentence_length and len(sentence_lengths) > 1
        else 0.0
    )
    punctuation = Counter(ch for ch in text if ch in ".,;:!?()[]{}\"'")
    repeated_words = sum(count - 1 for count in Counter(words).values() if count > 1)
    perplexity_proxy = math.exp(min(5.5, 2.0 + (repeated_words / max(1, len(words))) - vocabulary_diversity))
    passive_voice = len(PASSIVE_RE.findall(text)) / max(1, len(sentences))

    return {
        "perplexity": round(perplexity_proxy, 2),
        "vocabulary_diversity": round(vocabulary_diversity, 3),
        "average_sentence_length": round(average_sentence_length, 2) if average_sentence_length else None,
        "burstiness": round(burstiness, 3),
        "readability": _flesch_reading_ease(words, sentences),
        "passive_voice": round(passive_voice, 3),
        "pos_distribution": _pos_distribution(words),
        "punctuation": dict(punctuation),
    }
