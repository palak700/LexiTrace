from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis_service import analyze_text

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(payload: AnalysisRequest) -> AnalysisResponse:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text must not be empty.")
    if len(text) > settings.max_text_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Text is too long. Maximum allowed length is {settings.max_text_chars} characters.",
        )

    try:
        return analyze_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Analysis failed. Please try again.") from exc
