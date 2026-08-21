from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_input() -> None:
    response = client.post("/api/analyze", json={"text": "   "})
    assert response.status_code == 422


def test_short_input() -> None:
    response = client.post("/api/analyze", json={"text": "Hi"})
    assert response.status_code == 200
    body = response.json()
    assert body["model_name"] == "Development model"
    assert body["linguistic_features"]["perplexity"] is None


def test_normal_input_structure() -> None:
    text = "This proposal provides a comprehensive framework. It improves clarity and efficiency across the workflow."
    response = client.post("/api/analyze", json={"text": text})
    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] in {"Human", "AI-generated", "AI-polished human", "Humanized AI"}
    assert 0 <= body["confidence"] <= 1
    assert 0 <= body["ai_contribution"] <= 100
    assert set(body["class_probabilities"]) == {"human", "ai_generated", "ai_polished_human", "humanized_ai"}
    assert abs(sum(body["class_probabilities"].values()) - 1.0) < 0.02
    assert "pos_distribution" in body["linguistic_features"]
    assert body["explanation"]["method"] == "development heuristic explanation"


def test_invalid_input() -> None:
    response = client.post("/api/analyze", json={"content": "missing text key"})
    assert response.status_code == 422
