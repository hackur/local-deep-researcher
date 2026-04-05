"""
Authentication module — JWT-based auth for Local Deep Researcher SaaS.
Handles user registration, login, API key management, and JWT middleware.
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h
API_KEY_PREFIX = "ldr_"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# ── JWT Tokens ────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None

# ── API Key Management ────────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, key_hash, prefix)."""
    raw_key = f"{API_KEY_PREFIX}{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:12]
    return raw_key, key_hash, prefix

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    return hash_api_key(raw_key) == stored_hash
