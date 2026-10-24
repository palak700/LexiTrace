"""Account-scoped result snapshots. Source content requires explicit consent."""
import json
import hashlib
import uuid
from datetime import datetime, timezone

from app.api.auth import database


def history_database():
    db = database()
    db.execute('CREATE TABLE IF NOT EXISTS analysis_history ('
               'id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, '
               'result TEXT NOT NULL, document_text TEXT)')
    db.execute('CREATE INDEX IF NOT EXISTS history_user_date ON analysis_history(user_id, created_at DESC)')
    return db


def save_analysis(user_id, result, save_text=False):
    record_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    # Explicit allowlist: do not accidentally persist source text in new result fields.
    snapshot = {key: result[key] for key in (
        'prediction', 'confidence', 'class_probabilities', 'model_mode', 'model_name',
        'model_version', 'disclaimer', 'explanation_method',
    ) if key in result}
    snapshot['word_count'] = len(result['text'].split())
    snapshot['character_count'] = len(result['text'])
    snapshot['_source_hash'] = hashlib.sha256(result['text'].encode()).hexdigest()
    snapshot['sentences'] = result.get('sentences', []) if save_text else []
    db = history_database()
    try:
        db.execute('INSERT INTO analysis_history VALUES (?,?,?,?,?)', (
            record_id, user_id, created_at, json.dumps(snapshot), result['text'] if save_text else None,
        ))
        db.commit()
    finally:
        db.close()
    return {'history_id': record_id, 'created_at': created_at, 'text_saved': save_text}


def public_record(row):
    result = json.loads(row['result'])
    result.pop('_source_hash', None)
    return {'id': row['id'], 'created_at': row['created_at'],
            'text_saved': row['document_text'] is not None,
            'text': row['document_text'], 'result': result}


def check_explanation_source(record_id, user_id, text):
    from fastapi import HTTPException
    db = history_database()
    try:
        row = db.execute('SELECT result FROM analysis_history WHERE id=? AND user_id=?', (record_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Analysis not found.')
        if json.loads(row['result']).get('_source_hash') != hashlib.sha256(text.encode()).hexdigest():
            raise HTTPException(422, 'Explanation text does not match the saved analysis.')
    finally:
        db.close()


def save_explanation(record_id, user_id, explanation):
    db = history_database()
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT result FROM analysis_history WHERE id=? AND user_id=?', (record_id, user_id)).fetchone()
        if not row:
            return False
        snapshot = json.loads(row['result'])
        # Keep only interpretation metadata, never token text or source excerpts.
        snapshot['explanation'] = {key: explanation[key] for key in (
            'method', 'target_label', 'scope', 'partial', 'window_probability',
            'convergence_delta', 'disclaimer', 'approximation_warning',
        ) if key in explanation}
        db.execute('UPDATE analysis_history SET result=? WHERE id=? AND user_id=?',
                   (json.dumps(snapshot), record_id, user_id))
        db.commit()
        return True
    finally:
        db.close()
