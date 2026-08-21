from __future__ import annotations

from app.explainability.development import explain_development
from app.features.linguistic import analyze_linguistic_features
from app.ml.predictor import predict_text
from app.schemas.analysis import AnalysisResponse


def analyze_text(text: str) -> AnalysisResponse:
    prediction = predict_text(text)
    features = analyze_linguistic_features(text)
    explanation = explain_development(text)

    summary = (
        f"{prediction['prediction']} detected with {round(prediction['confidence'] * 100)}% confidence. "
        f"Running in {prediction['model_mode']} mode; results are for development use only."
    )

    return AnalysisResponse(
        prediction=prediction["prediction"],
        confidence=prediction["confidence"],
        ai_contribution=prediction["ai_contribution"],
        class_probabilities=prediction["probabilities"],
        linguistic_features=features,
        explanation=explanation,
        summary=summary,
        model_mode=prediction["model_mode"],
        model_name=prediction["model_name"],
    )
