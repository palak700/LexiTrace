import os
import re
import secrets
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from app.services.auth_service import (
    AuthRepository, AuthUnavailable, EmailExists, SESSION_SECONDS,
    hash_password, verify_password, token_hash,
)

router = APIRouter(prefix='/auth', tags=['accounts'])
COOKIE = 'lexitrace_session'

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        email = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Enter a valid email address.')
        return email

class RegistrationRequest(LoginRequest):
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=10, max_length=128)

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value):
        name = value.strip()
        if not name: raise ValueError('Name must not be blank.')
        return name

@lru_cache(maxsize=1)
def repository():
    try: return AuthRepository()
    except AuthUnavailable as exc: raise HTTPException(503, str(exc)) from exc

@lru_cache(maxsize=1)
def dummy_hash():
    return hash_password(secrets.token_urlsafe(32))

def require_user(request: Request, repo=Depends(repository)):
    token = request.cookies.get(COOKIE)
    try: user = repo.session_user(token_hash(token)) if token else None
    except SQLAlchemyError as exc: raise HTTPException(503, 'Account database is unavailable.') from exc
    if not user: raise HTTPException(401, 'Please sign in. Your session may have expired.')
    return user

def require_analysis_access(request: Request):
    # Guest access is limited to the untrained demo with no configured database.
    if os.getenv('LEXITRACE_MODE', 'demo') == 'demo' and not os.getenv('DATABASE_URL'):
        return None
    return require_user(request, repository())

def start_session(response, repo, user):
    token = secrets.token_urlsafe(32)
    repo.create_session(user['id'], token_hash(token))
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=os.getenv('LEXITRACE_COOKIE_SECURE', 'false').lower() == 'true',
                        samesite='lax', path='/')
    return {'user':{key:user[key] for key in ('id','name','email')}}

@router.get('/status')
def status():
    return {'accounts_configured':bool(os.getenv('DATABASE_URL')),
            'guest_allowed':os.getenv('LEXITRACE_MODE','demo')=='demo' and not os.getenv('DATABASE_URL')}

@router.post('/register', status_code=201)
def register(payload: RegistrationRequest, response: Response, repo=Depends(repository)):
    try:
        user = repo.create_user(payload.name, payload.email, hash_password(payload.password))
        return start_session(response, repo, user)
    except EmailExists as exc: raise HTTPException(409, str(exc)) from exc
    except SQLAlchemyError as exc: raise HTTPException(503, 'Account database is unavailable.') from exc

@router.post('/login')
def login(payload: LoginRequest, response: Response, repo=Depends(repository)):
    try:
        user = repo.find_user(payload.email)
        valid = verify_password(payload.password, user['password_hash'] if user else dummy_hash())
        if not user or not valid: raise HTTPException(401, 'Incorrect email or password.')
        return start_session(response, repo, user)
    except SQLAlchemyError as exc: raise HTTPException(503, 'Account database is unavailable.') from exc

@router.get('/me')
def me(user=Depends(require_user)):
    return {'user':user}

@router.post('/logout')
def logout(request: Request, response: Response, repo=Depends(repository)):
    token = request.cookies.get(COOKIE)
    try:
        if token: repo.delete_session(token_hash(token))
    except SQLAlchemyError as exc: raise HTTPException(503, 'Account database is unavailable.') from exc
    response.delete_cookie(COOKIE, path='/')
    return {'status':'signed out'}
