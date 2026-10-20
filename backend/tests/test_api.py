import os
os.environ['LEXITRACE_MODE'] = 'demo'
os.environ.pop('DATABASE_URL', None)
import hashlib
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv('LEXITRACE_AUTH_DB', str(tmp_path / 'accounts.sqlite3'))
    monkeypatch.setenv('LEXITRACE_ADMIN_SIGNUP_CODE', 'test-admin-code')
    with TestClient(app) as instance:
        yield instance

def register(client, **overrides):
    payload = {'name':'Test User', 'email':'user@example.com', 'password':'test-password-123', 'role':'user'}
    payload.update(overrides)
    return client.post('/api/auth/signup', json=payload)

@pytest.fixture
def signed_in(client):
    assert register(client).status_code == 201
    return client

def test_health_aliases(client):
    for prefix in ('', '/api'):
        response=client.get(prefix + '/health').json()
        assert response['status']=='ok'
        assert response['model']['mode']=='demo'
        assert response['model']['loaded'] is False

def test_analysis_requires_login(client):
    for prefix in ('', '/api'):
        for endpoint in ('/analyze', '/predict'):
            assert client.post(prefix + endpoint, json={'text':'A document.'}).status_code == 401

def test_validation(signed_in):
    for text in ('   ', 'x'*20001):
        assert signed_in.post('/api/analyze', json={'text':text}).status_code == 422


def test_explanation_access_validation_and_no_fabricated_demo_explanations(client):
    assert client.post('/api/explain', json={'text':'word '*50}).status_code == 401
    register(client)
    assert client.post('/api/explain', json={'text':'word '*49}).status_code == 422
    assert client.post('/api/explain', json={'text':'x'*20001}).status_code == 422
    assert client.post('/api/explain', json={'text':'word '*50}).status_code == 503


def test_explanation_routes_normalize_text_and_recover_from_failure(signed_in, monkeypatch):
    from app.api import routes
    from app.services import explanations
    monkeypatch.setenv('LEXITRACE_MODE', 'model')
    monkeypatch.setattr(routes, 'document_model', lambda path: object())
    def explain(classifier, text):
        assert text == ' '.join(['word']*50)
        return {'method':'Captum Integrated Gradients','tokens':[]}
    monkeypatch.setattr(explanations, 'explain_text', explain)
    for prefix in ('', '/api'):
        assert signed_in.post(prefix+'/explain', json={'text':' word\n '*50}).status_code == 200
    routes.explanation_lock.acquire()
    try:
        assert signed_in.post('/api/explain', json={'text':'word '*50}).status_code == 429
    finally:
        routes.explanation_lock.release()
    def fail(*args):
        raise RuntimeError('private submitted text')
    monkeypatch.setattr(explanations, 'explain_text', fail)
    response = signed_in.post('/api/explain', json={'text':'word '*50})
    assert response.status_code == 500
    assert 'private submitted text' not in response.text
    assert not routes.explanation_lock.locked()

def test_capabilities_match_validation(signed_in):
    limits = signed_in.get('/api/capabilities').json()
    assert limits['max_text_chars'] == 20000
    assert limits['min_words'] == 50
    assert limits['analysis_level'] == 'document'
    assert limits['upload_formats'] == ['.pdf', '.txt']
    assert limits['max_upload_bytes'] == 5 * 1024 * 1024
    document = 'word '*49 + 'x'*(limits['max_text_chars']-245)
    assert len(document) == limits['max_text_chars']
    assert signed_in.post('/api/analyze', json={'text':document}).status_code == 200
    assert signed_in.post('/api/analyze', json={'text':'x'*(limits['max_text_chars']+1)}).status_code == 422

def test_three_class_document_pipeline(signed_in):
    r = signed_in.post('/api/analyze', json={'text':'A comprehensive proposal. ' + 'word '*50 + 'I wrote this myself.'})
    assert r.status_code == 200
    b = r.json()
    assert set(b['class_probabilities']) == {'Human','AI-Generated','AI-Edited Human'}
    assert abs(sum(b['class_probabilities'].values())-1) < 1e-6
    assert b['analysis_level'] == 'document'
    assert b['sentences'] == []
    assert 'No sentence' in b['explanation_method']

def test_missing_models_fail_closed(signed_in, monkeypatch, tmp_path):
    monkeypatch.setenv('LEXITRACE_MODE','model')
    monkeypatch.setenv('LEXITRACE_DOCUMENT_MODEL', str(tmp_path/'missing'))
    assert signed_in.post('/analyze', json={'text':'A model request. ' + 'word '*50}).status_code == 503

def test_account_session_lifecycle(client, monkeypatch):
    response = register(client)
    assert response.status_code == 201
    assert response.json()['role'] == 'user'
    assert 'password' not in response.json()
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']
    assert client.get('/api/auth/me').json()['email'] == 'user@example.com'
    token = client.cookies.get('lexitrace_session')
    with sqlite3.connect(os.environ['LEXITRACE_AUTH_DB']) as db:
        stored = db.execute('SELECT password FROM users').fetchone()[0]
        assert stored != 'test-password-123'
        assert db.execute('SELECT token FROM sessions').fetchone()[0] == hashlib.sha256(token.encode()).hexdigest()
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/me').status_code == 401
    client.cookies.set('lexitrace_session', token)
    assert client.get('/api/auth/me').status_code == 401
    client.cookies.clear()
    assert client.post('/api/auth/login', json={'email':'USER@example.com','password':'test-password-123','role':'user'}).status_code == 200
    assert register(client).status_code == 409

def test_login_and_role_rejection(client):
    register(client)
    for overrides in ({'password':'wrong-password'}, {'role':'admin'}, {'email':'missing@example.com'}):
        payload = {'email':'user@example.com','password':'test-password-123','role':'user', **overrides}
        assert client.post('/api/auth/login', json=payload).status_code == 401
    assert register(client, email='other@example.com', role='superuser').status_code == 422

def test_admin_signup_requires_server_code(client, monkeypatch):
    assert register(client, role='admin').status_code == 403
    assert register(client, role='admin', admin_code='wrong').status_code == 403
    monkeypatch.delenv('LEXITRACE_ADMIN_SIGNUP_CODE')
    assert register(client, role='admin', admin_code='test-admin-code').status_code == 403
    monkeypatch.setenv('LEXITRACE_ADMIN_SIGNUP_CODE', 'test-admin-code')
    assert register(client, role='admin', admin_code='test-admin-code').json()['role'] == 'admin'
    assert client.get('/api/auth/me').json()['role'] == 'admin'

def test_expired_session(client):
    register(client)
    with sqlite3.connect(os.environ['LEXITRACE_AUTH_DB']) as db:
        db.execute('UPDATE sessions SET expires=0')
    assert client.get('/api/auth/me').status_code == 401

@pytest.mark.parametrize('word_count', [0, 1, 49, 50, 51])
def test_word_minimum_on_all_endpoints(signed_in, word_count):
    text = ' '.join(['word'] * word_count) if word_count else '   '
    for prefix in ('', '/api'):
        for endpoint in ('/analyze', '/predict'):
            response = signed_in.post(prefix + endpoint, json={'text':text})
            assert response.status_code == (200 if word_count >= 50 else 422)
            if word_count < 50:
                assert response.json()['detail'] == 'text too short'

@pytest.mark.parametrize('text', ['... '*50, '!!! ??? '*25])
def test_punctuation_only_rejected(signed_in, text):
    assert signed_in.post('/predict', json={'text':text}).status_code == 422

def test_predict_confidences(signed_in):
    result = signed_in.post('/predict', json={'text':'word '*50}).json()
    assert set(result['confidences']) == {'Human','AI-Generated','AI-Edited Human'}
    assert result['label'] in result['confidences']
    assert result['confidence'] == result['confidences'][result['label']]
    assert abs(sum(result['confidences'].values())-1) < 1e-6
    assert result['model_mode'] == 'demo'
    assert 'disclaimer' in result
    assert result.get('sentences',[]) == []

@pytest.mark.parametrize('label', ['Human','AI-Generated','AI-Edited Human'])
def test_predict_label_consistency(signed_in,monkeypatch,label):
    from app.api import routes
    monkeypatch.setattr(routes,'analyze',lambda text:{
        'prediction':label,'confidence':0.8,'class_probabilities':{key:(0.8 if key==label else 0.1) for key in ('Human','AI-Generated','AI-Edited Human')},
        'model_mode':'model','disclaimer':'Test disclaimer','sentences':[],
    })
    result=signed_in.post('/predict',json={'text':'word '*50}).json()
    assert result['label']==label
    assert result['confidences'][label]==0.8


def make_pdf(text='', encrypted=False):
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if text:
        font = DictionaryObject({NameObject('/Type'):NameObject('/Font'), NameObject('/Subtype'):NameObject('/Type1'), NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(('BT /F1 12 Tf 40 700 Td (' + text + ') Tj ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('test-password')
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_upload_and_prediction(signed_in):
    original = ' '.join(['word'] * 50)
    response = signed_in.post('/api/documents/extract', files={'file':('document.pdf',make_pdf(original),'application/pdf')})
    assert response.status_code == 200
    document = response.json()
    assert document['text'] == original
    assert document['word_count'] == 50
    assert document['filename'] == 'document.pdf'
    assert signed_in.post('/predict',json={'text':document['text']}).status_code == 200


def test_pdf_upload_requires_login(client):
    assert client.post('/api/documents/extract',files={'file':('document.pdf',b'%PDF-fake','application/pdf')}).status_code == 401


@pytest.mark.parametrize('name,content,message', [
    ('bad.pdf',b'not a PDF','not a valid PDF'),
    ('broken.pdf',b'%PDF-1.4 broken','Unable to read'),
    ('notes.docx',b'word '*50,'PDF or UTF-8'),
    ('empty.txt',b'','empty'),
    ('encoding.txt',b'\xff\xfe','UTF-8'),
    ('large.txt',b'x'*20001,'character limit'),
    ('oversize.pdf',b'x'*(5*1024*1024+1),'5 MB'),
], ids=['invalid-pdf','broken-pdf','unsupported-type','empty-file','invalid-encoding','text-limit','file-size-limit'])
def test_upload_rejections(signed_in,name,content,message):
    response = signed_in.post('/api/documents/extract',files={'file':(name,content)})
    assert response.status_code in (413,422)
    assert message in response.json()['detail']


def test_scanned_and_encrypted_pdfs(signed_in):
    response = signed_in.post('/api/documents/extract',files={'file':('scan.pdf',make_pdf())})
    assert response.status_code == 422
    assert 'OCR' in response.json()['detail']
    response = signed_in.post('/api/documents/extract',files={'file':('locked.pdf',make_pdf('word '*50,encrypted=True))})
    assert response.status_code == 422
    assert 'Password-protected' in response.json()['detail']


def test_uploaded_text_still_requires_50_words(signed_in):
    response = signed_in.post('/api/documents/extract',files={'file':('short.pdf',make_pdf('word '*49))})
    assert response.status_code == 200
    assert response.json()['word_count'] == 49
    prediction = signed_in.post('/predict',json={'text':response.json()['text']})
    assert prediction.status_code == 422
    assert prediction.json()['detail'] == 'text too short'


def test_utf8_text_upload(signed_in):
    original = 'word '*50
    response = signed_in.post('/api/documents/extract',files={'file':('notes.txt',original.encode('utf-8-sig'))})
    assert response.status_code == 200
    assert response.json()['text'] == original


def test_pdf_text_character_limit(signed_in):
    response = signed_in.post('/api/documents/extract',files={'file':('long.pdf',make_pdf('word '*4001))})
    assert response.status_code == 422
    assert 'character limit' in response.json()['detail']


@pytest.mark.parametrize('labels,indices', [
    (['Human','AI-Generated','AI-Edited Human'],[0,1,2]), (['AI-Edited Human','Human','AI-Generated'],[1,2,0]),
])
def test_document_checkpoint_label_mapping(labels,indices):
    from app.services.pipeline import canonical_label_indices
    assert canonical_label_indices(labels)==indices

@pytest.mark.parametrize('labels', [
    ['LABEL_0','LABEL_1','LABEL_2'], ['Human','Human','AI-Generated'], ['Human','AI-transformed'],
])
def test_invalid_document_checkpoint_labels(labels):
    from app.services.pipeline import canonical_label_indices,ModelUnavailable
    with pytest.raises(ModelUnavailable): canonical_label_indices(labels)


def test_model_mode_uses_only_document_classifier(signed_in,monkeypatch,tmp_path):
    from app.services import pipeline
    calls=[]
    class DocumentModel:
        def predict(self,text):
            calls.append(text)
            return [0.1,0.2,0.7]
    monkeypatch.setenv('LEXITRACE_MODE','model')
    monkeypatch.setenv('LEXITRACE_DOCUMENT_MODEL',str(tmp_path/'document'))
    monkeypatch.setattr(pipeline,'document_model',lambda path:DocumentModel())
    response=signed_in.post('/api/analyze',json={'text':'word '*50})
    assert response.status_code == 200
    result=response.json()
    assert result['prediction'] == 'AI-Edited Human'
    assert result['model_mode'] == 'model'
    assert result['model_name'] == 'DeBERTa-v3 document classifier'
    assert 'Demo' not in result['disclaimer']
    assert result.get('sentences',[]) == []
    assert len(calls) == 1


def test_model_loading_errors_return_503(signed_in,monkeypatch):
    from app.services import pipeline
    monkeypatch.setenv('LEXITRACE_MODE','model')
    def unavailable(path):
        raise pipeline.ModelUnavailable('Document checkpoint could not be loaded.')
    monkeypatch.setattr(pipeline,'document_model',unavailable)
    response=signed_in.post('/predict',json={'text':'word '*50})
    assert response.status_code == 503
    assert 'checkpoint' in response.json()['detail']


def test_supplied_three_class_checkpoint_is_compatible():
    from app.core.config import PROJECT_ROOT
    from app.services.pipeline import inspect_checkpoint
    path=PROJECT_ROOT/'ml/models/document'
    if not (path/'config.json').exists(): pytest.skip('Local checkpoint metadata unavailable')
    labels,indices=inspect_checkpoint(path)
    assert labels==['Human','AI-Generated','AI-Edited Human']
    assert indices==[0,1,2]


def test_readiness_reports_unavailable_checkpoint(client,monkeypatch,tmp_path):
    monkeypatch.setenv('LEXITRACE_MODE','model')
    monkeypatch.setenv('LEXITRACE_DOCUMENT_MODEL',str(tmp_path/'missing'))
    response=client.get('/api/ready')
    assert response.status_code==503
    assert response.json()['loaded'] is False
    assert response.json()['labels']==['Human','AI-Generated','AI-Edited Human']


def test_demo_has_no_fake_explanations(signed_in):
    result=signed_in.post('/predict',json={'text':'word '*50}).json()
    assert result['sentences']==[]
    assert result['model_mode']=='demo'
    assert 'Demo' in result['disclaimer']


def test_anonymous_analysis_is_configurable(client,monkeypatch):
    monkeypatch.setenv('LEXITRACE_ALLOW_ANONYMOUS','true')
    assert client.get('/api/capabilities').json()['allow_anonymous'] is True
    assert client.post('/predict',json={'text':'word '*50}).status_code==200
    assert client.get('/api/research/status').status_code==401
    assert client.post('/evaluate').status_code==401
    assert client.post('/api/documents/extract',files={'file':('notes.txt',b'word '*50)}).status_code==200


def test_research_admin_boundary(signed_in):
    assert signed_in.get('/api/research/status').status_code==403
    assert signed_in.post('/evaluate').status_code==403
    signed_in.post('/api/auth/logout')
    register(signed_in,email='admin@example.com',role='admin',admin_code='test-admin-code')
    status=signed_in.get('/api/research/status')
    assert status.status_code==200
    assert len(status.json()['versions'])==9
    assert all(version['report'] is None for version in status.json()['versions'])
    assert status.json()['fingerprint']['available'] is False
    assert signed_in.post('/evaluate').status_code in (409,503)


def test_optional_real_sentence_signals(signed_in,monkeypatch):
    from app.services import pipeline
    class Classifier:
        def predict(self,text): return [0.1,0.1,0.8]
    monkeypatch.setenv('LEXITRACE_MODE','model')
    monkeypatch.setenv('LEXITRACE_SENTENCE_EVIDENCE','true')
    monkeypatch.setattr(pipeline,'document_model',lambda path:Classifier())
    result=signed_in.post('/api/analyze',json={'text':'word '*50+'. Second sentence.'}).json()
    assert len(result['sentences'])==2
    for sentence in result['sentences']:
        assert result['text'][sentence['start']:sentence['end']]==sentence['sentence']
        assert sentence['tokens']==[]
        assert sentence['prediction']=='AI-Edited Human'



def test_admin_evaluation_uses_only_configured_paths(signed_in,monkeypatch,tmp_path):
    from app.api import research
    from ml.evaluation import evaluate
    signed_in.post('/api/auth/logout')
    register(signed_in,email='evaluation-admin@example.com',role='admin',admin_code='test-admin-code')
    monkeypatch.setenv('LEXITRACE_EVALUATION_DATA',str(tmp_path))
    monkeypatch.setenv('LEXITRACE_DOCUMENT_MODEL',str(tmp_path/'configured-model'))
    monkeypatch.setattr(research,'inspect_checkpoint',lambda path:None)
    seen=[]
    def run(data,model):
        seen.append((data,model))
        return {'labels':['Human','AI-Generated','AI-Edited Human'],'metrics':{'accuracy':.5},'sample_count':2}
    monkeypatch.setattr(evaluate,'run_evaluation',run)
    response=signed_in.post('/evaluate',json={'data':'C:/untrusted-data','model':'C:/untrusted-model'})
    assert response.status_code==200
    assert seen==[(str(tmp_path),str(tmp_path/'configured-model'))]


def test_research_reports_require_valid_metrics_and_same_test_hash(tmp_path,monkeypatch):
    import json
    from app.api.research import report_for,research_status
    monkeypatch.setenv('LEXITRACE_RESEARCH_DIR',str(tmp_path))
    report={'labels':['Human','AI-Generated','AI-Edited Human'],'sample_count':3,'metrics':{'accuracy':1.,'precision_macro':1.,'recall_macro':1.,'f1_macro':1.},
            'confusion_matrix':[[1,0,0],[0,1,0],[0,0,1]],'test_sha256':'a'*64,'split':'test','group_disjoint':True}
    (tmp_path/'v0.json').write_text(json.dumps(report))
    (tmp_path/'v1.json').write_text(json.dumps(report))
    assert report_for('v0')['status']=='measured'
    assert research_status()['comparisons_available'] is True
    report['test_sha256']='b'*64
    (tmp_path/'v1.json').write_text(json.dumps(report))
    assert research_status()['comparisons_available'] is False
    report['metrics']['accuracy']=2
    (tmp_path/'v1.json').write_text(json.dumps(report))
    assert report_for('v1')['status']=='invalid'


@pytest.mark.skipif(os.getenv('LEXITRACE_TEST_REAL_MODEL') != '1',reason='Enable LEXITRACE_TEST_REAL_MODEL=1 to load local weights.')
def test_real_checkpoint_predicts_through_api(signed_in,monkeypatch):
    from app.core.config import PROJECT_ROOT
    monkeypatch.setenv('LEXITRACE_MODE','model')
    monkeypatch.setenv('LEXITRACE_DOCUMENT_MODEL',str(PROJECT_ROOT/'ml/models/document'))
    ready=signed_in.get('/api/ready')
    assert ready.status_code==200,ready.text
    assert ready.json()['loaded'] is True
    text=('I visited the library yesterday to return a book and find something new to read. '
          'The librarian suggested a novel about a small town, and I spent the evening reading its first chapters. '
          'I enjoyed the quiet atmosphere and made a few notes about the characters before going to sleep.')
    response=signed_in.post('/predict',json={'text':text})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['model_mode']=='model'
    assert set(result['confidences'])=={'Human','AI-Generated','AI-Edited Human'}
    assert abs(sum(result['confidences'].values())-1)<1e-5
    assert result['label'] in result['confidences']
    assert result['confidence']==result['confidences'][result['label']]
    assert 'Demo' not in result['disclaimer']



def test_diagnostics_is_admin_only_and_uses_existing_input_validation(signed_in,monkeypatch):
    from app.services import prediction_diagnostics
    assert signed_in.post('/diagnose',json={'text':'word '*50}).status_code==403
    signed_in.post('/api/auth/logout')
    monkeypatch.setenv('LEXITRACE_ALLOW_ANONYMOUS','true')
    assert signed_in.post('/diagnose',json={'text':'word '*50}).status_code==401
    register(signed_in,email='diagnostics-admin@example.com',role='admin',admin_code='test-admin-code')
    assert signed_in.post('/api/diagnose',json={'text':'word '*49}).status_code==422
    assert signed_in.post('/api/diagnose',json={'text':'x'*20001}).status_code==422
    seen=[]
    monkeypatch.setattr(prediction_diagnostics,'diagnose_prediction',lambda text:seen.append(text) or {'production':{'label':'Human'}})
    response=signed_in.post('/api/diagnose',json={'text':'word '*50})
    assert response.status_code==200
    assert response.json()=={'production':{'label':'Human'}}
    assert seen==['word '*50]


def test_diagnostic_model_failure_is_safe(signed_in,monkeypatch):
    from app.services import prediction_diagnostics
    signed_in.post('/api/auth/logout')
    register(signed_in,email='diagnostic-errors@example.com',role='admin',admin_code='test-admin-code')
    def fail(text):
        raise RuntimeError('private input and computer-specific path must not escape')
    monkeypatch.setattr(prediction_diagnostics,'diagnose_prediction',fail)
    response=signed_in.post('/diagnose',json={'text':'word '*50})
    assert response.status_code==503
    assert 'private input' not in response.text


@pytest.mark.skipif(os.getenv('LEXITRACE_TEST_REAL_MODEL') != '1',reason='Enable real checkpoint tests explicitly.')
def test_real_diagnostics_compares_lengths_without_changing_prediction(signed_in,monkeypatch):
    from app.core.config import PROJECT_ROOT
    monkeypatch.setenv('LEXITRACE_MODE','model')
    monkeypatch.setenv('LEXITRACE_DOCUMENT_MODEL',str(PROJECT_ROOT/'ml/models/document'))
    signed_in.post('/api/auth/logout')
    register(signed_in,email='real-diagnostics@example.com',role='admin',admin_code='test-admin-code')
    text='word '*650
    prediction=signed_in.post('/predict',json={'text':text})
    assert prediction.status_code==200,prediction.text
    response=signed_in.post('/diagnose',json={'text':text})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['checkpoint']['evaluation_mode'] is True
    assert result['checkpoint']['saved_id2label']=={'0':'Human','1':'AI-Generated','2':'AI-Edited Human'}
    assert len(result['checkpoint']['sha256']['model.safetensors'])==64
    assert result['input']['normalized_token_count']>512
    assert result['production']['window_count']>1
    assert result['production']['document_truncated'] is False
    assert result['first_256_normalized']['tokens_processed']==256
    assert result['first_256_normalized']['truncated'] is True
    assert result['first_512_normalized']['tokens_processed']==512
    assert result['first_512_normalized']['truncated'] is True
    assert result['production']['label']==prediction.json()['label']
    assert result['production']['confidences']==pytest.approx(prediction.json()['confidences'],abs=1e-6)
    assert 'text' not in result
    assert 'token_ids' not in result
    for key in ('first_256_normalized','first_512_normalized','first_256_original'):
        assert sum(result[key]['confidences'].values())==pytest.approx(1,abs=1e-5)
