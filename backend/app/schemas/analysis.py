from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


class ClassProbabilities(BaseModel):
    human: float
    ai_generated: float
    ai_polished_human: float
    humanized_ai: float


class TokenEvidence(BaseModel):
    token: str
    score: float


class SentenceEvidence(BaseModel):
    sentence: str
    score: float


class Explanation(BaseModel):
    method: str
    important_sentences: list[SentenceEvidence]
    important_tokens: list[TokenEvidence]


class LinguisticFeatures(BaseModel):
    perplexity: float | None
    vocabulary_diversity: float | None
    average_sentence_length: float | None
    burstiness: float | None
    readability: float | None
    passive_voice: float | None
    pos_distribution: dict[str, float]
    punctuation: dict[str, int]


class AnalysisResponse(BaseModel):
    prediction: str
    confidence: float
    ai_contribution: int
    class_probabilities: ClassProbabilities
    linguistic_features: LinguisticFeatures
    explanation: Explanation
    summary: str
    model_mode: str
    model_name: str
    disclaimer: str = "AI text detection is probabilistic and should not be treated as definitive proof of authorship."
