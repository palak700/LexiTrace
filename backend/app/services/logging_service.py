"""Optional PostgreSQL logging; never persist submitted text or expose connection strings."""
import hashlib
import json
import logging
import os
from functools import lru_cache
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def engine_for(url):
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql':
        raise ValueError('PostgreSQL URL required')
    parsed = parsed.set(drivername='postgresql+psycopg')
    return create_engine(parsed, pool_pre_ping=True, connect_args={'connect_timeout': 3}, hide_parameters=True)


def engine():
    url = os.getenv('DATABASE_URL', '')
    return engine_for(url) if url else None


def database_status():
    if not os.getenv('DATABASE_URL'):
        return {'status': 'disabled', 'message': 'PostgreSQL analysis logging disabled; DATABASE_URL is not configured. Accounts use SQLite.'}
    try:
        with engine().connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'status': 'available', 'message': 'PostgreSQL connection available; analysis table is created on first stored analysis.'}
    except Exception as exc:
        logger.warning('PostgreSQL connectivity check failed (%s); connection details withheld.', type(exc).__name__)
        return {'status': 'unavailable', 'message': 'PostgreSQL is unavailable; analysis remains usable without logging.'}


def recent_analysis_logs(start_at=None, end_at=None, offset=0, limit=20):
    """Read only safe analysis metadata; never return hashes, evidence or raw errors."""
    empty = {'items': [], 'total': 0}
    if not os.getenv('DATABASE_URL'):
        return {**empty, 'status': 'disabled', 'message': 'Analysis logging is disabled. Configure PostgreSQL DATABASE_URL to record and view analysis activity.'}
    try:
        with engine().connect() as connection:
            if connection.execute(text("SELECT to_regclass('lexitrace_analysis')")).scalar() is None:
                return {**empty, 'status': 'available', 'message': 'Logging is connected. No analyses have been logged yet.'}
            clauses, args = [], {'offset': offset, 'limit': limit}
            if start_at:
                clauses.append('created_at >= :start_at')
                args['start_at'] = start_at
            if end_at:
                clauses.append('created_at <= :end_at')
                args['end_at'] = end_at
            where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
            total = connection.execute(text('SELECT COUNT(*) FROM lexitrace_analysis' + where), args).scalar()
            rows = connection.execute(text(
                'SELECT id, created_at, character_count, prediction, confidence, model_mode '
                'FROM lexitrace_analysis' + where + ' ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset'
            ), args).mappings().all()
            return {'status': 'available', 'message': 'Stored analysis activity. Dates are shown in your local time.',
                    'items': [dict(row) for row in rows], 'total': total}
    except Exception as exc:
        logger.warning('Analysis log read failed (%s); connection details withheld.', type(exc).__name__)
        return {**empty, 'status': 'unavailable', 'message': 'Analysis logs are temporarily unavailable. Check the PostgreSQL connection and try again.'}


class LoggingService:
    def store(self, result):
        try:
            db = engine()
            if db is None:
                return 'disabled: DATABASE_URL is unset'
            with db.begin() as connection:
                connection.execute(text('''CREATE TABLE IF NOT EXISTS lexitrace_analysis (
                  id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ DEFAULT now(),
                  text_sha256 TEXT NOT NULL, character_count INTEGER NOT NULL,
                  prediction TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                  model_mode TEXT NOT NULL, probabilities JSONB NOT NULL, evidence JSONB NOT NULL)'''))
                # Keep the existing schema, but never store sentence text or input content.
                connection.execute(text('''INSERT INTO lexitrace_analysis
                  (text_sha256,character_count,prediction,confidence,model_mode,probabilities,evidence)
                  VALUES (:hash,:length,:prediction,:confidence,:mode,CAST(:probs AS JSONB),CAST(:evidence AS JSONB))'''),
                  dict(hash=hashlib.sha256(result['text'].encode()).hexdigest(), length=len(result['text']),
                       prediction=result['prediction'], confidence=result['confidence'], mode=result['model_mode'],
                       probs=json.dumps(result['class_probabilities']), evidence='[]'))
            return 'stored'
        except Exception as exc:
            logger.warning('PostgreSQL analysis insert failed (%s); analysis returned without logging. Connection details withheld.', type(exc).__name__)
            return 'unavailable'
