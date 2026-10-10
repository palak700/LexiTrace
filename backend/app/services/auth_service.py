"""Password hashing and revocable PostgreSQL sessions."""
import hashlib
import hmac
import secrets
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.services.logging_service import engine

SESSION_SECONDS = 60 * 60 * 24

class AuthUnavailable(RuntimeError):
    pass

class EmailExists(ValueError):
    pass

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt${salt}${derived}'

def verify_password(password: str, stored: str) -> bool:
    try:
        kind, salt, expected = stored.split('$')
        if kind != 'scrypt': return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

class AuthRepository:
    def __init__(self):
        try:
            self.db = engine()
            if self.db is None: raise AuthUnavailable('Configure PostgreSQL DATABASE_URL to enable accounts.')
            with self.db.begin() as c:
                c.execute(text('''CREATE TABLE IF NOT EXISTS lexitrace_users (
                    id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())'''))
                c.execute(text('''CREATE TABLE IF NOT EXISTS lexitrace_sessions (
                    token_hash TEXT PRIMARY KEY, user_id BIGINT NOT NULL REFERENCES lexitrace_users(id) ON DELETE CASCADE,
                    expires_at TIMESTAMPTZ NOT NULL)'''))
        except AuthUnavailable:
            raise
        except Exception as exc:
            raise AuthUnavailable('Account database is unavailable. Check PostgreSQL configuration.') from exc

    def create_user(self, name, email, password_hash):
        try:
            with self.db.begin() as c:
                return dict(c.execute(text('''INSERT INTO lexitrace_users (name,email,password_hash)
                    VALUES (:name,:email,:password) RETURNING id,name,email'''),
                    {'name':name,'email':email,'password':password_hash}).mappings().one())
        except IntegrityError as exc:
            raise EmailExists('An account with this email already exists.') from exc

    def find_user(self, email):
        with self.db.connect() as c:
            user = c.execute(text('SELECT id,name,email,password_hash FROM lexitrace_users WHERE email=:email'),
                             {'email':email}).mappings().first()
            return dict(user) if user else None

    def create_session(self, user_id, hashed_token):
        with self.db.begin() as c:
            c.execute(text('DELETE FROM lexitrace_sessions WHERE expires_at <= now()'))
            c.execute(text('''INSERT INTO lexitrace_sessions (token_hash,user_id,expires_at)
                VALUES (:token,:user,now()+interval '24 hours')'''), {'token':hashed_token,'user':user_id})

    def session_user(self, hashed_token):
        with self.db.connect() as c:
            user = c.execute(text('''SELECT u.id,u.name,u.email FROM lexitrace_sessions s
                JOIN lexitrace_users u ON u.id=s.user_id
                WHERE s.token_hash=:token AND s.expires_at>now()'''), {'token':hashed_token}).mappings().first()
            return dict(user) if user else None

    def delete_session(self, hashed_token):
        with self.db.begin() as c:
            c.execute(text('DELETE FROM lexitrace_sessions WHERE token_hash=:token'), {'token':hashed_token})
