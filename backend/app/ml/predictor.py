from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.contribution.estimator import estimate_ai_contribution
from ml.inference.predict import development_predict_text, model_predict_text


def predict_text(text: str) -> dict:
    mode = os.getenv("LEXITRACE_MODE", "development").lower()
    model_path = Path(os.getenv("LEXITRACE_MODEL_PATH", "../ml/models/deberta-v3-base-finetuned"))

    if mode == "model" and model_path.exists():
        result = model_predict_text(text, model_path)
        model_mode = "model"
        model_name = "DeBERTa-v3-base fine-tuned"
    else:
        result = development_predict_text(text)
        model_mode = "development"
        model_name = "Development model"

    ai_contribution = estimate_ai_contribution(result["probabilities"], _feature_hints(text))
    return {
        "prediction": result["prediction"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "ai_contribution": ai_contribution,
        "model_mode": model_mode,
        "model_name": model_name,
    }


def _feature_hints(text: str) -> dict[str, float]:
    words = re.findall(r"\b[\w'-]+\b", text.lower())
    sentences = [item for item in re.split(r"[.!?]+", text) if item.strip()]
    avg_sentence_length = len(words) / max(1, len(sentences))
    unique_ratio = len(set(words)) / max(1, len(words))
    return {
        "average_sentence_length": avg_sentence_length,
        "vocabulary_diversity": unique_ratio,
        "length": len(words),
    }
