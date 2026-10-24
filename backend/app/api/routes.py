import os
import logging
from io import BytesIO
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.api.auth import analysis_access
from app.core.config import settings, document_model_path
from app.core.labels import LABELS
from app.services.pipeline import ModelUnavailable, analyze, model_status, current_mode, document_model, load_lock, normalize_text


logger = logging.getLogger(__name__)
router = APIRouter()
explanation_lock = Lock()


class AnalysisRequest(BaseModel):
    save_text: bool = False
    history_id: str | None = Field(default=None, max_length=32)
    text: str = Field(
        min_length=1,
        max_length=settings.max_text_chars,
    )


@router.post('/explain')
def explain_route(payload: AnalysisRequest, user=Depends(analysis_access)):
    if len(payload.text.split()) < 50:
        raise HTTPException(422, 'text too short')
    if not any(character.isalnum() for character in payload.text):
        raise HTTPException(422, 'Text must contain letters or numbers.')
    if current_mode() != 'model':
        raise HTTPException(503, 'Explanations require the trained model; test-mode explanations are unavailable.')
    if payload.history_id:
        if not user:
            raise HTTPException(401, 'Sign in to attach an explanation to history.')
        from app.services.history import check_explanation_source
        check_explanation_source(payload.history_id, user['id'], normalize_text(payload.text))
    if not explanation_lock.acquire(blocking=False):
        raise HTTPException(429, 'Another explanation is running. Please try again shortly.')
    try:
        from app.services.explanations import explain_text
        with load_lock:
            classifier = document_model(document_model_path())
        result = explain_text(classifier, normalize_text(payload.text))
        if payload.history_id:
            from app.services.history import save_explanation
            try:
                result['history_explanation_saved'] = save_explanation(payload.history_id, user['id'], result)
            except Exception:
                logger.error('Explanation history update failed; source and error details withheld.')
                result['history_explanation_saved'] = False
        return result
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception:
        logger.error('Attribution failed; input and exception details withheld to protect submitted text.')
        raise HTTPException(500, 'Unable to compute token attributions. Check the backend configuration.')
    finally:
        explanation_lock.release()


@router.get('/health')
def health():
    return {'status': 'ok', 'model': model_status(load=False)}


@router.get('/capabilities')
def capabilities():
    return {
        'max_text_chars': settings.max_text_chars,
        'min_words': 50,
        'labels': LABELS,
        'allow_anonymous': os.getenv('LEXITRACE_ALLOW_ANONYMOUS', str(settings.allow_anonymous)).lower() == 'true',
        'upload_formats': ['.pdf', '.txt'],
        'max_upload_bytes': 5 * 1024 * 1024,
        'analysis_level': 'document',
        'model_mode': os.getenv('LEXITRACE_MODE', settings.mode),
    }


@router.post('/analyze')
def analyze_route(payload: AnalysisRequest, user=Depends(analysis_access)):
    if len(payload.text.split()) < 50:
        raise HTTPException(422, 'text too short')

    if not any(character.isalnum() for character in payload.text):
        raise HTTPException(422, 'Text must contain letters or numbers.')

    try:
        result = analyze(payload.text)
    except ModelUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception:
        logger.error('Analysis failed; input and exception details withheld to protect submitted text.')
        raise HTTPException(
            500,
            'Analysis failed. Check backend configuration and logs.',
        )

    if user:
        from app.services.history import save_analysis
        try:
            result.update(save_analysis(user['id'], result, payload.save_text))
            result['history_saved'] = True
        except Exception:
            logger.error('History save failed; source text and error details withheld.')
            result['history_saved'] = False
    return result


@router.post('/predict')
def predict_route(payload: AnalysisRequest, user=Depends(analysis_access)):
    result = analyze_route(payload, user)

    return {
        'label': result['prediction'],
        'confidence': result['confidence'],
        'confidences': {
            label: score
            for label, score in result['class_probabilities'].items()
        },
        'model_mode': result['model_mode'],
        **{key: result[key] for key in ('history_id', 'created_at', 'text_saved', 'history_saved', 'model_name', 'model_version') if key in result},
        'disclaimer': result['disclaimer'],
        'sentences': result.get('sentences', []),
        'explanation_method': result.get('explanation_method', 'No explanations available.'),
    }


@router.post('/documents/extract')
def extract_document(file: UploadFile = File(...), user=Depends(analysis_access)):
    extension = Path(file.filename or '').suffix.lower()

    if extension not in ('.pdf', '.txt'):
        raise HTTPException(
            422,
            'Please upload a PDF or UTF-8 .txt file.',
        )

    content = file.file.read(5 * 1024 * 1024 + 1)

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            413,
            'File is too large. Maximum upload size is 5 MB.',
        )

    if not content:
        raise HTTPException(422, 'This document is empty.')

    if extension == '.pdf':
        if not content.startswith(b'%PDF-'):
            raise HTTPException(422, 'This file is not a valid PDF.')

        try:
            reader = PdfReader(BytesIO(content))

            if reader.is_encrypted:
                raise HTTPException(
                    422,
                    'Password-protected PDFs are not supported. '
                    'Upload an unlocked copy.',
                )

            if len(reader.pages) > 100:
                raise HTTPException(
                    422,
                    'PDFs may contain at most 100 pages.',
                )

            parts = []
            length = 0

            for page in reader.pages:
                part = page.extract_text() or ''
                parts.append(part)
                length += len(part) + (1 if len(parts) > 1 else 0)

                if length > settings.max_text_chars:
                    raise HTTPException(
                        422,
                        f'Extracted text exceeds the '
                        f'{settings.max_text_chars:,} character limit.',
                    )

            text = '\n'.join(parts).strip()

        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                422,
                'Unable to read this PDF. Upload a valid, unlocked PDF.',
            ) from exc

        if not text:
            raise HTTPException(
                422,
                'No readable text found. Scanned PDFs need OCR before uploading.',
            )

    else:
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise HTTPException(
                422,
                'Save the text document as UTF-8 and try again.',
            ) from exc

        if '\0' in text:
            raise HTTPException(
                422,
                'Please upload a plain text document.',
            )

    if not text.strip():
        raise HTTPException(422, 'This document is empty.')

    if len(text) > settings.max_text_chars:
        raise HTTPException(
            422,
            f'Extracted text exceeds the '
            f'{settings.max_text_chars:,} character limit.',
        )

    return {
        'text': text,
        'filename': file.filename,
        'word_count': len(text.split()),
        'character_count': len(text),
    }

@router.get('/ready')
def readiness():
    from fastapi.responses import JSONResponse
    status = model_status(load=True)
    return JSONResponse(status_code=200 if status['ready'] else 503, content=status)
