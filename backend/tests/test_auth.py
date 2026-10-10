import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api import auth
from app.services.auth_service import hash_password, verify_password, token_hash, EmailExists

class MemoryRepository:
    """Test double for PostgreSQL storage; no application in-memory account mode."""
    def __init__(self): self.users={}; self.sessions={}
    def create_user(self,name,email,password_hash):
        if email in self.users: raise EmailExists('An account with this email already exists.')
        user={'id':len(self.users)+1,'name':name,'email':email,'password_hash':password_hash}
        self.users[email]=user
        return {k:user[k] for k in ('id','name','email')}
    def find_user(self,email): return self.users.get(email)
    def create_session(self,user_id,hashed_token): self.sessions[hashed_token]=user_id
    def session_user(self,hashed_token):
        uid=self.sessions.get(hashed_token)
        return next(({k:u[k] for k in ('id','name','email')} for u in self.users.values() if u['id']==uid),None)
    def delete_session(self,hashed_token): self.sessions.pop(hashed_token,None)

@pytest.fixture
def setup(monkeypatch):
    repo=MemoryRepository()
    app.dependency_overrides[auth.repository]=lambda:repo
    monkeypatch.setattr(auth,'repository',lambda:repo)
    monkeypatch.setenv('DATABASE_URL','postgresql://test-placeholder')
    with TestClient(app) as client: yield client,repo
    app.dependency_overrides.clear()

def test_password_hashing():
    first=hash_password('a-long-test-password');second=hash_password('a-long-test-password')
    assert first != second
    assert verify_password('a-long-test-password',first)
    assert not verify_password('wrong-password',first)
    assert not verify_password('anything','invalid')

def test_register_login_logout_and_revocation(setup):
    c,repo=setup
    payload={'name':'Aryan','email':' ARYAN@example.com ','password':'secure-test-password'}
    r=c.post('/api/auth/register',json=payload)
    assert r.status_code==201 and r.json()['user']['email']=='aryan@example.com'
    assert 'password' not in str(r.json())
    assert 'HttpOnly' in r.headers['set-cookie']
    token=c.cookies.get(auth.COOKIE)
    assert token_hash(token) in repo.sessions and token not in repo.sessions
    assert c.get('/api/auth/me').status_code==200
    assert c.post('/api/auth/register',json=payload).status_code==409
    assert c.post('/api/auth/logout').status_code==200
    assert c.get('/api/auth/me').status_code==401
    c.cookies.set(auth.COOKIE,token)
    assert c.get('/api/auth/me').status_code==401
    c.cookies.clear()
    assert c.post('/api/auth/login',json={'email':'aryan@example.com','password':'wrong'}).status_code==401
    assert c.post('/api/auth/login',json={'email':'unknown@example.com','password':'wrong'}).status_code==401
    assert c.post('/api/auth/login',json={'email':'aryan@example.com','password':payload['password']}).status_code==200

def test_validation_and_analysis_requires_login(setup):
    c,_=setup
    assert c.post('/api/auth/register',json={'name':'   ','email':'bad','password':'short'}).status_code==422
    assert c.post('/api/analyze',json={'text':'A protected analysis.'}).status_code==401

def test_demo_status_without_database(monkeypatch):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.setenv('LEXITRACE_MODE','demo')
    auth.repository.cache_clear()
    with TestClient(app) as c:
        assert c.get('/api/auth/status').json()=={'accounts_configured':False,'guest_allowed':True}
        assert c.post('/api/auth/login',json={'email':'aryan@example.com','password':'password'}).status_code==503
