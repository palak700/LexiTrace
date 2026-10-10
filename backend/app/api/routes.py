from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.pipeline import analyze, ModelUnavailable
router = APIRouter()
class AnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
@router.get('/health')
def health(): return {'status':'ok'}
@router.post('/analyze')
def analyze_route(payload: AnalysisRequest):
    if not payload.text.strip(): raise HTTPException(422, 'Text must not be empty.')
    try: return analyze(payload.text)
    except ModelUnavailable as e: raise HTTPException(503, str(e)) from e
    except Exception as e: raise HTTPException(500, 'Analysis failed. Check backend configuration and logs.') from e
