from __future__ import annotations

import re
from collections import Counter


TOKEN_RE = re.compile(r"\b[\w'-]+\b")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
AI_STYLE_TERMS = {
    "moreover",
    "furthermore",
    "therefore",
    "efficiency",
    "robust",
    "comprehensive",
    "optimize",
    "streamline",
    "leverage",
    "notably",
    "ultimately",
}


def explain_development(text: str) -> dict:
    sentences = [item.strip() for item in SENTENCE_RE.findall(text) if item.strip()]
    words = [word.lower() for word in TOKEN_RE.findall(text)]
    counts = Counter(words)

    sentence_scores = []
    for sentence in sentences:
        tokens = [word.lower() for word in TOKEN_RE.findall(sentence)]
        if not tokens:
            continue
        style_hits = sum(1 for token in tokens if token in AI_STYLE_TERMS)
        uniformity = 1.0 / max(1, abs(len(tokens) - 18) + 1)
        score = min(1.0, (style_hits * 0.2) + uniformity)
        sentence_scores.append({"sentence": sentence, "score": round(score, 3)})

    token_scores = []
    for token, count in counts.items():
        if len(token) < 5:
            continue
        score = min(1.0, (0.2 if token in AI_STYLE_TERMS else 0.0) + (count / max(1, len(words))) + (len(token) / 80))
        token_scores.append({"token": token, "score": round(score, 3)})

    return {
        "method": "development heuristic explanation",
        "important_sentences": sorted(sentence_scores, key=lambda item: item["score"], reverse=True)[:3],
        "important_tokens": sorted(token_scores, key=lambda item: item["score"], reverse=True)[:8],
    }
