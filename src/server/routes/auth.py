"""
Authentication routes — registration, login, API key management.
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Query
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import uuid

from ollama_deep_researcher.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── In-memory store (replace with PostgreSQL in production) ──────────────────

_users: dict[str, dict] = {}
_api_keys: dict[str, dict] = {}

# ── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str

class ApiKeyResponse(BaseModel):
    key: str
    prefix: str
    name: str

class ApiKeyListResponse(BaseModel):
    keys: list[dict]

# ── Auth Dependency ──────────────────────────────────────────────────────────

async def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract and validate JWT from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id not in _users:
        raise HTTPException(status_code=401, detail="User not found")

    return _users[user_id]

# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """Register a new user account."""
    # Check if email already exists
    for user in _users.values():
        if user["email"] == req.email:
            raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    _users[user_id] = {
        "id": user_id,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "display_name": req.display_name or req.email.split("@")[0],
        "created_at": str(__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
    }

    token = create_access_token(user_id, req.email)
    return TokenResponse(access_token=token, user_id=user_id, email=req.email)

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login with email and password."""
    user = None
    for u in _users.values():
        if u["email"] == req.email:
            user = u
            break

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=token, user_id=user["id"], email=user["email"])

@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(name: str = Query(..., min_length=1, max_length=100), user: dict = Depends(get_current_user)):
    """Generate a new API key for the authenticated user."""
    raw_key, key_hash, prefix = generate_api_key()
    key_id = str(uuid.uuid4())

    _api_keys[key_id] = {
        "id": key_id,
        "user_id": user["id"],
        "name": name,
        "key_hash": key_hash,
        "prefix": prefix,
        "created_at": str(__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
    }

    return ApiKeyResponse(key=raw_key, prefix=prefix, name=name)

@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(user: dict = Depends(get_current_user)):
    """List all API keys for the authenticated user."""
    user_keys = [
        {"id": k["id"], "name": k["name"], "prefix": k["prefix"], "created_at": k["created_at"]}
        for k in _api_keys.values()
        if k["user_id"] == user["id"]
    ]
    return ApiKeyListResponse(keys=user_keys)

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, user: dict = Depends(get_current_user)):
    """Revoke an API key."""
    if key_id not in _api_keys or _api_keys[key_id]["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="API key not found")

    del _api_keys[key_id]
    return {"message": "API key revoked"}
