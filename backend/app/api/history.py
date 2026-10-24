from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.auth import current_user
from app.services.history import history_database, public_record

router = APIRouter(prefix='/history')


@router.get('')
def list_history(start_date: date | None = None, end_date: date | None = None,
                 offset: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
                 user=Depends(current_user)):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, 'Start date must be on or before end date.')
    conditions, args = ['user_id=?'], [user['id']]
    # Date filters are UTC calendar dates, inclusive at both ends.
    if start_date:
        conditions.append('created_at>=?')
        args.append(datetime.combine(start_date, time.min, timezone.utc).isoformat())
    if end_date:
        conditions.append('created_at<=?')
        args.append(datetime.combine(end_date, time.max, timezone.utc).isoformat())
    where = ' AND '.join(conditions)
    db = history_database()
    try:
        total = db.execute(f'SELECT COUNT(*) FROM analysis_history WHERE {where}', args).fetchone()[0]
        rows = db.execute(f'SELECT * FROM analysis_history WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?',
                          [*args, limit, offset]).fetchall()
        # Keep source text out of the list endpoint; it is available in the detail view.
        items = [{key: value for key, value in public_record(row).items() if key != 'text'} for row in rows]
        return {'items': items, 'total': total}
    finally:
        db.close()


def owned_record(record_id, user_id):
    db = history_database()
    try:
        row = db.execute('SELECT * FROM analysis_history WHERE id=? AND user_id=?', (record_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Analysis not found.')
        return public_record(row)
    finally:
        db.close()


@router.get('/{record_id}')
def get_history(record_id: str, user=Depends(current_user)):
    return owned_record(record_id, user['id'])


@router.delete('/{record_id}', status_code=204)
def delete_history(record_id: str, user=Depends(current_user)):
    db = history_database()
    try:
        cursor = db.execute('DELETE FROM analysis_history WHERE id=? AND user_id=?', (record_id, user['id']))
        if not cursor.rowcount:
            raise HTTPException(404, 'Analysis not found.')
        db.commit()
        return Response(status_code=204)
    finally:
        db.close()


@router.get('/{record_id}/report.pdf')
def download_report(record_id: str, user=Depends(current_user)):
    record = owned_record(record_id, user['id'])
    from app.services.reports import build_report
    return Response(build_report(record), media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="lexitrace-{record["id"]}.pdf"',
        'Cache-Control': 'no-store',
    })
