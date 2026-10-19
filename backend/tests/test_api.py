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
        assert client.get(prefix + '/health').json() == {'status':'ok'}

def test_analysis_requires_login(client):
    for prefix in ('', '/api'):
        for endpoint in ('/analyze', '/predict'):
            assert client.post(prefix + endpoint, json={'text':'A document.'}).status_code == 401

def test_validation(signed_in):
    for text in ('   ', 'x'*20001):
        assert signed_in.post('/api/analyze', json={'text':text}).status_code == 422

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

def test_three_class_sentence_pipeline(signed_in):
    r = signed_in.post('/api/analyze', json={'text':'A comprehensive proposal. ' + 'word '*50 + 'I wrote this myself.'})
    assert r.status_code == 200
    b = r.json()
    assert set(b['class_probabilities']) == {'Human-Written','AI-Generated','AI-Transformed'}
    assert abs(sum(b['class_probabilities'].values())-1) < 1e-6
    assert len(b['sentences']) == 2
    for s in b['sentences']:
        assert b['text'][s['start']:s['end']] == s['sentence']
    assert all(not s['tokens'] for s in b['sentences'])

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
    assert set(result['confidences']) == {'Human', 'AI-Generated', 'AI-Edited Human'}
    assert result['label'] in result['confidences']
    assert result['confidence'] == result['confidences'][result['label']]
    assert abs(sum(result['confidences'].values())-1) < 1e-6
    assert result['model_mode'] == 'demo'
    assert 'disclaimer' in result
    assert 'sentences' not in result

@pytest.mark.parametrize('source,expected', [
    ('Human-Written','Human'), ('AI-Generated','AI-Generated'), ('AI-Transformed','AI-Edited Human')
])
def test_predict_label_mapping(signed_in, monkeypatch, source, expected):
    from app.api import routes
    monkeypatch.setattr(routes, 'analyze', lambda text: {
        'prediction':source, 'confidence':0.8,
        'class_probabilities':{key:(0.8 if key == source else 0.1) for key in routes.DISPLAY_LABELS},
        'model_mode':'model', 'disclaimer':'Test disclaimer',
    })
    result = signed_in.post('/predict', json={'text':'word '*50}).json()
    assert result['label'] == expected
    assert result['confidences'][expected] == 0.8


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
