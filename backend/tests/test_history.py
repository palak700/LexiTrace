import json
import sqlite3
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api import auth, routes, history


SOURCE = ('Private source document. ' + 'word '*60).strip()


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('LEXITRACE_AUTH_DB', str(tmp_path/'history.sqlite3'))
    monkeypatch.setenv('LEXITRACE_ALLOW_ANONYMOUS', 'false')
    def analyze(text):
        return {'text':text, 'prediction':'Human', 'confidence':0.7,
                'class_probabilities':{'Human':0.7,'AI-Generated':0.2,'AI-Edited Human':0.1},
                'model_mode':'model','model_name':'Test classifier','model_version':'sha256:test-checkpoint',
                'disclaimer':'Signals, not proof. Scores are not accuracy.',
                'explanation_method':'Document classifier on sentence fragments.',
                'sentences':[{'sentence':text,'prediction':'Human','score':0.7}],
                'unexpected_source_copy':text}
    monkeypatch.setattr(routes, 'analyze', analyze)
    app = FastAPI()
    app.include_router(auth.router, prefix='/api')
    app.include_router(routes.router, prefix='/api')
    app.include_router(history.router, prefix='/api')
    with TestClient(app) as instance:
        yield instance


def register(client, email='first@example.com'):
    response = client.post('/api/auth/signup', json={
        'name':'Test User','email':email,'password':'test-password','role':'user',
    })
    assert response.status_code == 201


def analyze(client, **options):
    response = client.post('/api/analyze', json={'text':SOURCE, **options})
    assert response.status_code == 200
    assert response.json()['history_saved'] is True
    return response.json()['history_id']


def test_results_only_by_default_and_explicit_text_consent(client):
    register(client)
    first = analyze(client)
    detail = client.get('/api/history/'+first).json()
    assert detail['text'] is None and detail['text_saved'] is False
    assert detail['result']['sentences'] == []
    assert SOURCE not in json.dumps(detail)
    assert detail['result']['class_probabilities']['Human'] == 0.7
    assert detail['result']['model_version'] == 'sha256:test-checkpoint'
    second = analyze(client, save_text=True)
    detail = client.get('/api/history/'+second).json()
    assert detail['text'] == SOURCE and detail['text_saved'] is True
    assert detail['result']['sentences'][0]['sentence'] == SOURCE
    records = client.get('/api/history').json()
    assert records['total'] == 2 and records['items'][0]['id'] == second
    assert 'text' not in records['items'][0]
    assert 'unexpected_source_copy' not in detail['result']


def test_history_is_private_including_report_and_delete(client):
    register(client)
    record_id = analyze(client)
    client.post('/api/auth/logout')
    for path in ('/api/history','/api/history/'+record_id,'/api/history/'+record_id+'/report.pdf'):
        assert client.get(path).status_code == 401
    assert client.delete('/api/history/'+record_id).status_code == 401
    register(client, 'second@example.com')
    assert client.get('/api/history').json()['items'] == []
    assert client.get('/api/history/'+record_id).status_code == 404
    assert client.get('/api/history/'+record_id+'/report.pdf').status_code == 404
    assert client.delete('/api/history/'+record_id).status_code == 404
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'email':'first@example.com','password':'test-password','role':'user'})
    assert client.delete('/api/history/'+record_id).status_code == 204
    assert client.get('/api/history').json()['total'] == 0
    assert client.get('/api/history/'+record_id).status_code == 404
    assert client.get('/api/history/'+record_id+'/report.pdf').status_code == 404


def test_inclusive_date_filter_and_pagination(client):
    import os
    register(client)
    first = analyze(client)
    second = analyze(client)
    with sqlite3.connect(os.environ['LEXITRACE_AUTH_DB']) as db:
        db.execute('UPDATE analysis_history SET created_at=? WHERE id=?', ('2026-10-01T00:00:00+00:00', first))
        db.execute('UPDATE analysis_history SET created_at=? WHERE id=?', ('2026-10-24T23:59:59.999999+00:00', second))
    page = client.get('/api/history?start_date=2026-10-24&end_date=2026-10-24').json()
    assert page['total'] == 1 and page['items'][0]['id'] == second
    assert client.get('/api/history?end_date=2026-09-30').json()['total'] == 0
    page = client.get('/api/history?limit=1&offset=1').json()
    assert page['total'] == 2 and page['items'][0]['id'] == first
    for query in ('start_date=invalid','start_date=2026-11-01&end_date=2026-10-01','offset=-1','limit=101'):
        assert client.get('/api/history?'+query).status_code == 422


def test_pdf_uses_saved_result_not_current_model_and_omits_private_text(client, monkeypatch):
    register(client)
    record_id = analyze(client)
    def fail(*args):
        raise AssertionError('Report must not run inference again')
    monkeypatch.setattr(routes, 'analyze', fail)
    response = client.get('/api/history/'+record_id+'/report.pdf')
    assert response.status_code == 200 and response.headers['content-type'] == 'application/pdf'
    assert 'attachment' in response.headers['content-disposition']
    assert response.headers['cache-control'] == 'no-store'
    assert response.content.startswith(b'%PDF-')
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    for value in ('Human','AI-Generated','AI-Edited Human','70.0%','20.0%','10.0%',
                  'sha256:test-checkpoint','UTC','Explanation','Signals, not proof'):
        assert value in text
    assert 'Private source document' not in text


def test_logged_in_history_with_guest_access_enabled_and_no_guest_records(client, monkeypatch):
    monkeypatch.setenv('LEXITRACE_ALLOW_ANONYMOUS', 'true')
    response = client.post('/api/predict',json={'text':SOURCE,'save_text':True})
    assert response.status_code == 200 and 'history_id' not in response.json()
    register(client)
    response = client.post('/api/predict',json={'text':SOURCE})
    assert response.json()['history_saved'] is True
    assert client.get('/api/history').json()['total'] == 1


def test_failed_history_save_keeps_prediction_but_reports_failure(client, monkeypatch):
    from app.services import history as storage
    register(client)
    def fail(*args):
        raise OSError('private database details')
    monkeypatch.setattr(storage,'save_analysis',fail)
    response = client.post('/api/predict',json={'text':SOURCE})
    assert response.status_code == 200
    assert response.json()['history_saved'] is False
    assert 'private database details' not in response.text
    assert 'history_id' not in response.json()


def test_generated_explanation_summary_attaches_only_to_matching_owned_result(client, monkeypatch):
    from app.services import explanations
    register(client)
    record_id = analyze(client)
    monkeypatch.setattr(routes, 'current_mode', lambda:'model')
    monkeypatch.setattr(routes, 'document_model', lambda path:object())
    monkeypatch.setattr(explanations, 'explain_text', lambda *args:{
        'method':'Captum Integrated Gradients','target_label':'Human',
        'scope':'First model window only.','window_probability':0.73,
        'convergence_delta':0.001,'disclaimer':'Explains model response only.',
        'approximation_warning':False,'text':SOURCE,
        'tokens':[{'text':SOURCE, 'attribution':0.5}],
    })
    response = client.post('/api/explain', json={'text':SOURCE,'history_id':record_id})
    assert response.status_code == 200 and response.json()['history_explanation_saved'] is True
    detail = client.get('/api/history/'+record_id).json()
    assert detail['result']['explanation']['method'] == 'Captum Integrated Gradients'
    assert 'tokens' not in detail['result']['explanation']
    assert 'Private source document' not in json.dumps(detail)
    pdf = client.get('/api/history/'+record_id+'/report.pdf')
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
    assert 'Captum Integrated Gradients' in text and '73.0%' in text
    assert 'Private source document' not in text
    assert client.post('/api/explain', json={'text':'different '*60,'history_id':record_id}).status_code == 422
    client.post('/api/auth/logout')
    register(client,'other@example.com')
    assert client.post('/api/explain', json={'text':SOURCE,'history_id':record_id}).status_code == 404
