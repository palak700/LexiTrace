"""Local accounts with hashed passwords and revocable cookie sessions."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix='/auth')
COOKIE = 'lexitrace_session'

def database():
    db = sqlite3.connect(os.getenv('LEXITRACE_AUTH_DB', str(Path(__file__).resolve().parents[2] / 'accounts.sqlite3')))
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL)')
    return db

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()

def public_user(row):
    return {key: row[key] for key in ('id', 'name', 'email', 'role')}

def current_user(request: Request):
    token = request.cookies.get(COOKIE, '')
    db = database()
    try:
        row = db.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token=? AND sessions.expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    finally:
        db.close()
    if not row:
        raise HTTPException(401, 'Please sign in to continue.')
    return public_user(row)

def start_session(db, response, user_id):
    token = secrets.token_urlsafe(32)
    db.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
    db.execute('INSERT INTO sessions VALUES (?, ?, ?)', (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time() + 86400))
    db.commit()
    response.set_cookie(COOKIE, token, httponly=True, samesite='strict', secure=os.getenv('LEXITRACE_COOKIE_SECURE') == 'true', max_age=86400, path='/')

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern='^(user|admin)$')

class Registration(Credentials):
    name: str = Field(min_length=1, max_length=100)
    admin_code: str = Field(default='', max_length=256)

@router.post('/signup', status_code=201)
def signup(payload: Registration, response: Response):
    email = payload.email.strip().lower()
    if not payload.name.strip() or '@' not in email or not email.rsplit('@', 1)[1]:
        raise HTTPException(422, 'Enter a name and a valid email address.')
    if payload.role == 'admin':
        code = os.getenv('LEXITRACE_ADMIN_SIGNUP_CODE', '')
        if not code or not hmac.compare_digest(code.encode(), payload.admin_code.encode()):
            raise HTTPException(403, 'Admin signup requires a valid administrator setup code.')
    db = database()
    try:
        try:
            cursor = db.execute('INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)', (payload.name.strip(), email, password_hash(payload.password), payload.role))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, 'An account with this email already exists.') from exc
        start_session(db, response, cursor.lastrowid)
        return public_user(db.execute('SELECT * FROM users WHERE id=?', (cursor.lastrowid,)).fetchone())
    finally:
        db.close()

@router.post('/login')
def login(payload: Credentials, response: Response):
    db = database()
    try:
        row = db.execute('SELECT * FROM users WHERE email=?', (payload.email.strip().lower(),)).fetchone()
        stored = row['password'] if row else password_hash('dummy-password')
        valid = hmac.compare_digest(stored, password_hash(payload.password, stored.split(':')[0]))
        if not row or not valid or row['role'] != payload.role:
            raise HTTPException(401, 'Email, password, or account type is incorrect.')
        start_session(db, response, row['id'])
        return public_user(row)
    finally:
        db.close()

@router.get('/me')
def me(user=Depends(current_user)):
    return user

@router.post('/logout')
def logout(request: Request, response: Response):
    db = database()
    try:
        db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(request.cookies.get(COOKIE, '').encode()).hexdigest(),))
        db.commit()
    finally:
        db.close()
    response.delete_cookie(COOKIE, path='/')
    return {'status': 'ok'}



def analysis_access(request: Request):
    from app.core.config import settings
    if os.getenv('LEXITRACE_ALLOW_ANONYMOUS', str(settings.allow_anonymous)).lower() == 'true':
        return None
    return current_user(request)


def require_admin(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required.')
    return user
