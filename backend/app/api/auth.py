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
from app.services.email_verification import send_admin_code

router = APIRouter(prefix='/auth')
COOKIE = 'lexitrace_session'

def database():
    db = sqlite3.connect(os.getenv('LEXITRACE_AUTH_DB', str(Path(__file__).resolve().parents[2] / 'accounts.sqlite3')))
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS admin_challenges (token TEXT PRIMARY KEY, user_id INTEGER UNIQUE NOT NULL, code_hash TEXT NOT NULL, expires REAL NOT NULL, sent_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0)')
    return db


def challenge_hash(token, code):
    return hashlib.sha256(f'{token}:{code}'.encode()).hexdigest()


def start_admin_verification(db, row):
    # Serialize issuance so concurrent requests cannot bypass the cooldown.
    if not db.in_transaction:
        db.execute('BEGIN IMMEDIATE')
    now = time.time()
    previous = db.execute('SELECT sent_at FROM admin_challenges WHERE user_id=?', (row['id'],)).fetchone()
    if previous and now - previous['sent_at'] < 60:
        raise HTTPException(429, 'Please wait 60 seconds before requesting another code.')
    token = secrets.token_urlsafe(32)
    code = f'{secrets.randbelow(1000000):06d}'
    try:
        send_admin_code(row['email'], code)
    except Exception as exc:
        raise HTTPException(503, 'Unable to send the verification email. Please contact the administrator or try again later.') from exc
    db.execute('DELETE FROM admin_challenges WHERE expires<=? OR user_id=?', (now, row['id']))
    db.execute('INSERT INTO admin_challenges (token,user_id,code_hash,expires,sent_at) VALUES (?,?,?,?,?)',
               (hashlib.sha256(token.encode()).hexdigest(), row['id'], challenge_hash(token, code), now + 600, now))
    db.commit()
    return {'verification_required': True, 'challenge_id': token, 'expires_in': 600}

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


class AdminVerification(BaseModel):
    challenge_id: str = Field(min_length=40, max_length=128)
    code: str = Field(pattern=r'^[0-9]{6}$')

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
        row = db.execute('SELECT * FROM users WHERE id=?', (cursor.lastrowid,)).fetchone()
        if row['role'] == 'admin':
            # Keep the account available for a login retry if email delivery fails.
            db.commit()
            return start_admin_verification(db, row)
        start_session(db, response, row['id'])
        return public_user(row)
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
        if row['role'] == 'admin':
            return start_admin_verification(db, row)
        start_session(db, response, row['id'])
        return public_user(row)
    finally:
        db.close()

@router.post('/verify-admin')
def verify_admin(payload: AdminVerification, response: Response):
    db = database()
    try:
        db.execute('BEGIN IMMEDIATE')
        token_hash = hashlib.sha256(payload.challenge_id.encode()).hexdigest()
        challenge = db.execute('SELECT * FROM admin_challenges WHERE token=?', (token_hash,)).fetchone()
        if not challenge or challenge['expires'] <= time.time() or challenge['attempts'] >= 5:
            raise HTTPException(401, 'Verification expired or unavailable. Sign in again to request a new code.')
        if not hmac.compare_digest(challenge['code_hash'], challenge_hash(payload.challenge_id, payload.code)):
            db.execute('UPDATE admin_challenges SET attempts=attempts+1 WHERE token=?', (token_hash,))
            db.commit()
            raise HTTPException(401, 'Incorrect verification code. After 5 incorrect attempts, request a new code.')
        row = db.execute('SELECT * FROM users WHERE id=? AND role=?', (challenge['user_id'], 'admin')).fetchone()
        if not row:
            raise HTTPException(401, 'Administrator account is unavailable.')
        db.execute('DELETE FROM admin_challenges WHERE token=?', (token_hash,))
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
