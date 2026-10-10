import os
import hashlib
import logging
from functools import lru_cache

@lru_cache(maxsize=1)
def engine():
    from sqlalchemy import create_engine
    url = os.getenv('DATABASE_URL')
    if not url: return None
    if not url.startswith(('postgresql://','postgresql+psycopg://')):
        raise ValueError('DATABASE_URL must use PostgreSQL.')
    return create_engine(url.replace('postgresql://','postgresql+psycopg://',1), pool_pre_ping=True)

class LoggingService:
    def store(self, result):
        from sqlalchemy import text
        db = engine()
        if db is None: return 'disabled: DATABASE_URL is unset'
        try:
            with db.begin() as c:
                c.execute(text("""CREATE TABLE IF NOT EXISTS lexitrace_analysis (
                  id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ DEFAULT now(),
                  text_sha256 TEXT NOT NULL, character_count INTEGER NOT NULL,
                  prediction TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                  model_mode TEXT NOT NULL, probabilities JSONB NOT NULL, evidence JSONB NOT NULL)"""))
                import json
                summary = [{k:s[k] for k in ('start','end','prediction','score')} for s in result['sentences']]
                c.execute(text("""INSERT INTO lexitrace_analysis
                  (text_sha256,character_count,prediction,confidence,model_mode,probabilities,evidence)
                  VALUES (:hash,:length,:prediction,:confidence,:mode,CAST(:probs AS JSONB),CAST(:evidence AS JSONB))"""),
                  dict(hash=hashlib.sha256(result['text'].encode()).hexdigest(),length=len(result['text']),
                       prediction=result['prediction'],confidence=result['confidence'],mode=result['model_mode'],
                       probs=json.dumps(result['class_probabilities']),evidence=json.dumps(summary)))
            return 'stored'
        except Exception:
            logging.getLogger(__name__).warning('PostgreSQL logging failed; analysis remains available.')
            return 'unavailable'
