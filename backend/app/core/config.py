import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / 'backend/.env', override=False)

@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv('LEXITRACE_MODE', 'model')
    document_model_path: str = os.getenv('LEXITRACE_DOCUMENT_MODEL', str(PROJECT_ROOT / 'ml/models/document'))
    frontend_origin: str = os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')
    max_text_chars: int = int(os.getenv('LEXITRACE_MAX_TEXT_CHARS', '20000'))
    allow_anonymous: bool = os.getenv('LEXITRACE_ALLOW_ANONYMOUS', 'false').lower() == 'true'

def configured_path(value):
    path = Path(value).expanduser()
    return str(path if path.is_absolute() else PROJECT_ROOT / 'backend' / path)


def document_model_path():
    return configured_path(os.getenv('LEXITRACE_DOCUMENT_MODEL', settings.document_model_path))


settings = Settings()
