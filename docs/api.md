# API

Base URL: `http://localhost:8000/api`

## GET /health

Response:

```json
{
  "status": "ok"
}
```

## POST /analyze

Request:

```json
{
  "text": "some text"
}
```

Response:

```json
{
  "prediction": "AI-polished human",
  "confidence": 0.89,
  "ai_contribution": 72,
  "class_probabilities": {
    "human": 0.08,
    "ai_generated": 0.15,
    "ai_polished_human": 0.72,
    "humanized_ai": 0.05
  },
  "linguistic_features": {
    "perplexity": 18.7,
    "vocabulary_diversity": 0.42,
    "average_sentence_length": 17.4,
    "burstiness": 0.18,
    "readability": 61,
    "passive_voice": 0.24,
    "pos_distribution": {},
    "punctuation": {}
  },
  "explanation": {
    "method": "development heuristic explanation",
    "important_sentences": [],
    "important_tokens": []
  },
  "summary": "...",
  "model_mode": "development",
  "model_name": "Development model",
  "disclaimer": "AI text detection is probabilistic and should not be treated as definitive proof of authorship."
}
```

## Error Handling

- Empty or invalid text returns `422`.
- Text longer than the configured limit returns `413`.
- Internal errors return a safe generic `500` message without raw stack traces.
