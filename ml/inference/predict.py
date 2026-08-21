from __future__ import annotations

import math
import re
from pathlib import Path

LABELS = {
    0: "Human",
    1: "AI-generated",
    2: "AI-polished human",
    3: "Humanized AI",
}
PROBABILITY_KEYS = ["human", "ai_generated", "ai_polished_human", "humanized_ai"]


def development_predict_text(text: str) -> dict:
    words = re.findall(r"\b[\w'-]+\b", text.lower())
    sentences = [item.strip() for item in re.split(r"[.!?]+", text) if item.strip()]
    avg_sentence_length = len(words) / max(1, len(sentences))
    unique_ratio = len(set(words)) / max(1, len(words))
    ai_terms = sum(
        1
        for word in words
        if word
        in {
            "comprehensive",
            "furthermore",
            "moreover",
            "therefore",
            "efficiency",
            "optimize",
            "streamline",
            "robust",
            "leverage",
            "notably",
        }
    )
    uniformity = 1 / (1 + _sentence_length_variance(sentences))

    human = 0.38 + (0.25 * unique_ratio) - (0.04 * ai_terms)
    ai_generated = 0.18 + (0.12 * uniformity) + (0.04 * ai_terms)
    ai_polished = 0.2 + (0.06 * ai_terms) + (0.004 * max(0, avg_sentence_length - 14))
    humanized_ai = 0.24 + (0.08 * (1 - uniformity)) + (0.04 if unique_ratio > 0.72 else 0)
    probabilities = _normalize([human, ai_generated, ai_polished, humanized_ai])
    index = max(range(4), key=lambda item: probabilities[item])

    return {
        "prediction": LABELS[index],
        "confidence": round(probabilities[index], 2),
        "probabilities": {
            key: round(probabilities[position], 2)
            for position, key in enumerate(PROBABILITY_KEYS)
        },
    }


def model_predict_text(text: str, model_path: Path) -> dict:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.eval()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**inputs).logits[0]
    probabilities_tensor = torch.softmax(logits, dim=-1)
    probabilities = probabilities_tensor.cpu().tolist()
    index = int(torch.argmax(probabilities_tensor).item())
    return {
        "prediction": LABELS[index],
        "confidence": round(float(probabilities[index]), 4),
        "probabilities": {
            key: round(float(probabilities[position]), 4)
            for position, key in enumerate(PROBABILITY_KEYS)
        },
    }


def predict_text(text: str) -> dict:
    return development_predict_text(text)


def _normalize(values: list[float]) -> list[float]:
    cleaned = [max(0.01, value) for value in values]
    total = sum(cleaned)
    return [value / total for value in cleaned]


def _sentence_length_variance(sentences: list[str]) -> float:
    lengths = [len(re.findall(r"\b[\w'-]+\b", sentence)) for sentence in sentences]
    if len(lengths) < 2:
        return 0.5
    mean = sum(lengths) / len(lengths)
    return math.sqrt(sum((length - mean) ** 2 for length in lengths) / len(lengths)) / max(1, mean)
