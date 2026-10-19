import logging

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, Field
from app.services.pipeline import analyze, ModelUnavailable
from app.api.auth import current_user
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class AnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=settings.max_text_chars)

@router.get('/health')
def health():
    return {'status': 'ok'}

@router.get('/capabilities')
def capabilities():
    return {'max_text_chars': settings.max_text_chars, 'min_words': 50, 'upload_formats': ['.pdf', '.txt'], 'max_upload_bytes': 5 * 1024 * 1024, 'analysis_level': 'document'}

@router.post('/analyze')
def analyze_route(payload: AnalysisRequest, user=Depends(current_user)):
    if len(payload.text.split()) < 50:
        raise HTTPException(422, 'text too short')
    if not any(character.isalnum() for character in payload.text):
        raise HTTPException(422, 'Text must contain letters or numbers.')
    try:
        return analyze(payload.text)
    except ModelUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, 'Analysis failed. Check backend configuration and logs.') from e


DISPLAY_LABELS = {
    'Human-Written': 'Human',
    'AI-Generated': 'AI-Generated',
    'AI-Transformed': 'AI-Edited Human',
}

@router.post('/predict')
def predict_route(payload: AnalysisRequest, user=Depends(current_user)):
    result = analyze_route(payload, user)
    return {
        'label': DISPLAY_LABELS[result['prediction']],
        'confidence': result['confidence'],
        'confidences': {DISPLAY_LABELS[label]: score for label, score in result['class_probabilities'].items()},
        'model_mode': result['model_mode'],
        'disclaimer': result['disclaimer'],
    }


@router.post('/documents/extract')
def extract_document(file: UploadFile = File(...), user=Depends(current_user)):
    from io import BytesIO
    from pathlib import Path
    from pypdf import PdfReader
    extension = Path(file.filename or '').suffix.lower()
    if extension not in ('.pdf', '.txt'):
        raise HTTPException(422, 'Please upload a PDF or UTF-8 .txt file.')
    content = file.file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, 'File is too large. Maximum upload size is 5 MB.')
    if not content:
        raise HTTPException(422, 'This document is empty.')
    if extension == '.pdf':
        if not content.startswith(b'%PDF-'):
            raise HTTPException(422, 'This file is not a valid PDF.')
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise HTTPException(422, 'Password-protected PDFs are not supported. Upload an unlocked copy.')
            if len(reader.pages) > 100:
                raise HTTPException(422, 'PDFs may contain at most 100 pages.')
            parts = []
            length = 0
            for page in reader.pages:
                part = page.extract_text() or ''
                parts.append(part)
                length += len(part) + (1 if len(parts) > 1 else 0)
                if length > settings.max_text_chars:
                    raise HTTPException(422, f'Extracted text exceeds the {settings.max_text_chars:,} character limit.')
            text = '\n'.join(parts).strip()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, 'Unable to read this PDF. Upload a valid, unlocked PDF.') from exc
        if not text:
            raise HTTPException(422, 'No readable text found. Scanned PDFs need OCR before uploading.')
    else:
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise HTTPException(422, 'Save the text document as UTF-8 and try again.') from exc
        if '\0' in text:
            raise HTTPException(422, 'Please upload a plain text document.')
    if not text.strip():
        raise HTTPException(422, 'This document is empty.')
    if len(text) > settings.max_text_chars:
        raise HTTPException(422, f'Extracted text exceeds the {settings.max_text_chars:,} character limit.')
    return {'text': text, 'filename': file.filename, 'word_count': len(text.split()), 'character_count': len(text)}
