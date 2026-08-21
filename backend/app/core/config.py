import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("LEXITRACE_MODE", "development")
    model_path: str = os.getenv("LEXITRACE_MODEL_PATH", "../ml/models/deberta-v3-base-finetuned")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    max_text_chars: int = int(os.getenv("LEXITRACE_MAX_TEXT_CHARS", "20000"))


settings = Settings()
