import hashlib
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import auth


@pytest.fixture
def flow(monkeypatch, tmp_path):
    path = tmp_path / 'auth.sqlite3'
    monkeypatch.setenv('LEXITRACE_AUTH_DB', str(path))
    monkeypatch.setenv('LEXITRACE_ADMIN_SIGNUP_CODE', 'setup-secret')
    sent = []
    monkeypatch.setattr(auth, 'send_admin_code', lambda email, code: sent.append((email, code)))
    app = FastAPI()
    app.include_router(auth.router)
    with TestClient(app) as client:
        yield client, sent, path


def signup(client):
    return client.post('/auth/signup', json={
        'name': 'Admin', 'email': 'admin@example.com', 'password': 'test-password',
        'role': 'admin', 'admin_code': 'setup-secret',
    })


def login(client, **overrides):
    return client.post('/auth/login', json={
        'email': 'admin@example.com', 'password': 'test-password', 'role': 'admin', **overrides,
    })


def verify(client, challenge, code):
    return client.post('/auth/verify-admin', json={'challenge_id': challenge, 'code': code})


def test_signup_and_login_require_single_use_email_code(flow):
    client, sent, path = flow
    response = signup(client)
    assert response.status_code == 201
    challenge = response.json()['challenge_id']
    assert 'set-cookie' not in response.headers
    assert client.get('/auth/me').status_code == 401
    email, code = sent[-1]
    assert email == 'admin@example.com'
    assert len(code) == 6 and code.isdigit()
    assert code not in response.text
    with sqlite3.connect(path) as db:
        stored = db.execute('SELECT token, code_hash FROM admin_challenges').fetchone()
        assert stored[0] == hashlib.sha256(challenge.encode()).hexdigest()
        assert stored[1] != code
        assert db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] == 0
    assert verify(client, challenge, code).json()['role'] == 'admin'
    assert client.get('/auth/me').status_code == 200
    client.post('/auth/logout')
    assert verify(client, challenge, code).status_code == 401
    assert login(client, password='wrong-password').status_code == 401
    assert len(sent) == 1
    response = login(client)
    assert response.json()['verification_required'] is True
    assert client.get('/auth/me').status_code == 401
    assert verify(client, response.json()['challenge_id'], sent[-1][1]).status_code == 200


def test_attempt_limit_expiry_and_replacement(flow):
    client, sent, path = flow
    challenge = signup(client).json()['challenge_id']
    code = sent[-1][1]
    wrong = '000000' if code != '000000' else '111111'
    for _ in range(5):
        assert verify(client, challenge, wrong).status_code == 401
    assert verify(client, challenge, code).status_code == 401
    assert login(client).status_code == 429
    assert len(sent) == 1
    with sqlite3.connect(path) as db:
        db.execute('UPDATE admin_challenges SET sent_at=sent_at-61')
    replacement = login(client).json()['challenge_id']
    assert replacement != challenge
    assert verify(client, challenge, code).status_code == 401
    with sqlite3.connect(path) as db:
        db.execute('UPDATE admin_challenges SET expires=0')
    assert verify(client, replacement, sent[-1][1]).status_code == 401
    assert client.get('/auth/me').status_code == 401


def test_delivery_failure_does_not_grant_access_and_login_can_retry(flow, monkeypatch):
    client, sent, path = flow
    def fail(*args):
        raise RuntimeError('private SMTP credentials')
    monkeypatch.setattr(auth, 'send_admin_code', fail)
    response = signup(client)
    assert response.status_code == 503
    assert 'private SMTP' not in response.text
    assert client.get('/auth/me').status_code == 401
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] == 0
    monkeypatch.setattr(auth, 'send_admin_code', lambda email, code: sent.append((email, code)))
    challenge = login(client).json()['challenge_id']
    assert verify(client, challenge, sent[-1][1]).status_code == 200


def test_code_validation_and_unknown_challenge(flow):
    client, _, _ = flow
    for code in ('12345', '1234567', 'abcdef'):
        assert verify(client, 'x'*43, code).status_code == 422
    assert verify(client, 'x'*43, '123456').status_code == 401


@pytest.mark.parametrize('security,port', [('starttls', 587), ('ssl', 465)])
def test_smtp_delivery_uses_tls(monkeypatch, security, port):
    from app.services import email_verification as mail
    for key, value in {'HOST': 'smtp.example.com', 'USERNAME': 'smtp-user',
                       'PASSWORD': 'smtp-secret', 'FROM': 'sender@example.com',
                       'SECURITY': security}.items():
        monkeypatch.setenv('LEXITRACE_SMTP_' + key, value)
    monkeypatch.delenv('LEXITRACE_SMTP_PORT', raising=False)
    calls = []
    class SMTP:
        def __init__(self, host, actual_port, **kwargs):
            assert (host, actual_port) == ('smtp.example.com', port)
            if security == 'ssl':
                assert 'context' in kwargs
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def starttls(self, **kwargs):
            calls.append('tls')
        def login(self, username, password):
            assert (username, password) == ('smtp-user', 'smtp-secret')
            calls.append('login')
        def send_message(self, message):
            assert message['To'] == 'admin@example.com'
            assert message['From'] == 'sender@example.com'
            assert '012345' in message.get_content()
            calls.append('send')
    monkeypatch.setattr(mail.smtplib, 'SMTP', SMTP)
    monkeypatch.setattr(mail.smtplib, 'SMTP_SSL', SMTP)
    mail.send_admin_code('admin@example.com', '012345')
    assert calls == (['tls', 'login', 'send'] if security == 'starttls' else ['login', 'send'])


def test_missing_smtp_configuration_fails_closed(monkeypatch):
    from app.services.email_verification import send_admin_code
    monkeypatch.delenv('LEXITRACE_SMTP_HOST', raising=False)
    with pytest.raises(RuntimeError, match='not configured'):
        send_admin_code('admin@example.com', '012345')
