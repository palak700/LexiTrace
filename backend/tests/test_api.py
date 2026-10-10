import os
os.environ['LEXITRACE_MODE']='demo'
os.environ.pop('DATABASE_URL',None)
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health_aliases():
    for prefix in ('','/api'): assert client.get(prefix+'/health').json()=={'status':'ok'}
def test_validation():
    for text in ('   ','x'*20001): assert client.post('/api/analyze',json={'text':text}).status_code==422
def test_three_class_sentence_pipeline():
    r=client.post('/api/analyze',json={'text':'A comprehensive proposal. I wrote this myself.'})
    assert r.status_code==200
    b=r.json(); assert set(b['class_probabilities'])=={'Human-Written','AI-Generated','AI-Transformed'}
    assert abs(sum(b['class_probabilities'].values())-1)<1e-6
    assert len(b['sentences'])==2
    for s in b['sentences']: assert b['text'][s['start']:s['end']]==s['sentence']
    assert all(not s['tokens'] for s in b['sentences'])
def test_missing_models_fail_closed(monkeypatch,tmp_path):
    monkeypatch.setenv('LEXITRACE_MODE','model'); monkeypatch.setenv('LEXITRACE_DOCUMENT_MODEL',str(tmp_path/'missing'))
    assert client.post('/analyze',json={'text':'A model request.'}).status_code==503
