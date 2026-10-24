from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.auth import require_admin
from app.services.logging_service import recent_analysis_logs

router = APIRouter(prefix='/admin', dependencies=[Depends(require_admin)])


@router.get('/logs')
def analysis_logs(response: Response, start_date: date | None = None, end_date: date | None = None,
                  offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, 'Start date must be on or before end date.')
    response.headers['Cache-Control'] = 'no-store'
    return recent_analysis_logs(
        datetime.combine(start_date, time.min, timezone.utc) if start_date else None,
        datetime.combine(end_date, time.max, timezone.utc) if end_date else None,
        offset, limit,
    )
