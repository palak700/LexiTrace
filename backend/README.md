# LexiTrace Backend

FastAPI service for health checks and text analysis.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:LEXITRACE_MODE="development"
uvicorn app.main:app --reload --port 8000
```

## Test

```powershell
pytest
```
