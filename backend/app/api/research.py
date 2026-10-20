"""Protected measured evaluation; no invented benchmark or fingerprint values."""
import json
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import require_admin
from app.api.routes import AnalysisRequest
from app.core.config import settings, configured_path, document_model_path
from app.core.labels import LABELS
from app.services.pipeline import ModelUnavailable, inspect_checkpoint, model_status
from app.services.logging_service import database_status

router=APIRouter(dependencies=[Depends(require_admin)])


def report_for(version):
    directory=os.getenv('LEXITRACE_RESEARCH_DIR')
    if not directory:
        return {'version':version,'status':'missing','report':None}
    path=Path(configured_path(directory))/f'{version}.json'
    if not path.is_file():
        return {'version':version,'status':'missing','report':None}
    try:
        report=json.loads(path.read_text(encoding='utf-8'))
        metrics=report['metrics']
        matrix=report['confusion_matrix']
        valid=(report['labels']==LABELS and report['group_disjoint'] is True and report['split']=='test'
               and len(report['test_sha256'])==64 and report['sample_count']>0
               and all(isinstance(metrics[key],(int,float)) and 0<=metrics[key]<=1 for key in ('accuracy','precision_macro','recall_macro','f1_macro'))
               and len(matrix)==len(LABELS) and all(len(row)==len(LABELS) for row in matrix)
               and all(isinstance(value,int) and value>=0 for row in matrix for value in row)
               and sum(map(sum,matrix))==report['sample_count'])
        if not valid:
            raise ValueError('Invalid measured report')
        # Expose only metrics and reproducibility metadata, not arbitrary local-file contents.
        report={key:report[key] for key in ('labels','metrics','confusion_matrix','sample_count','test_sha256','split','group_disjoint')}
        return {'version':version,'status':'measured','report':report}
    except (OSError,ValueError,KeyError,TypeError):
        return {'version':version,'status':'invalid','report':None}


@router.get('/research/status')
def research_status():
    versions=[report_for(f'v{index}') for index in range(9)]
    hashes={item['report']['test_sha256'] for item in versions if item['report']}
    return {'model':model_status(load=False),'database':database_status(),'versions':versions,
            'comparisons_available':len(hashes)==1 and sum(item['status']=='measured' for item in versions)>1,
            'evaluation_configured':bool(os.getenv('LEXITRACE_EVALUATION_DATA')),
            'fingerprint':{'available':False,'message':'Transformation Fingerprint is pending its corrected-SRS definition and suitable paired data; no fingerprint is fabricated.'}}


@router.post('/evaluate')
def evaluate():
    model_path=document_model_path()
    try:
        inspect_checkpoint(model_path)
    except ModelUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
    data=os.getenv('LEXITRACE_EVALUATION_DATA')
    data = configured_path(data) if data else None
    if not data or not Path(data).is_dir():
        raise HTTPException(409,'Configure LEXITRACE_EVALUATION_DATA with grouped train/validation/test CSV files. No benchmark results are available.')
    try:
        from ml.evaluation.evaluate import run_evaluation
        return run_evaluation(data,model_path)
    except ModelUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
    except ValueError as exc:
        # Validation errors contain no document text or credentials.
        raise HTTPException(422,str(exc)) from exc
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error('Held-out evaluation failed (%s). No report returned.',type(exc).__name__)
        raise HTTPException(503,'Evaluation could not complete. Check configured data, compatible three-class model and ML dependencies.') from exc


@router.post('/diagnose')
def diagnose(payload: AnalysisRequest):
    from app.services.prediction_diagnostics import diagnose_prediction
    if len(payload.text.split())<50:
        raise HTTPException(422,'text too short')
    if not any(character.isalnum() for character in payload.text):
        raise HTTPException(422,'Text must contain letters or numbers.')
    try:
        return diagnose_prediction(payload.text)
    except ModelUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error('Prediction diagnostics failed (%s); submitted text and file paths withheld.',type(exc).__name__)
        raise HTTPException(503,'Diagnostics could not complete. Check checkpoint files and ML dependencies.') from exc
