"""
Auth primitives: password hashing (bcrypt), JWT issue/verify, and the
`get_current_user` dependency that turns a Bearer token into a stable user_id.

The user_id is the account UUID minted at signup — it never changes, so it's the
stable cross-session key for the long-term memory store.
"""

import os
import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-change-me")
JWT_ALG = "HS256"
TOKEN_TTL_DAYS = 7  # long-lived so tokens don't expire mid-demo

_bearer = HTTPBearer(auto_error=True)


def _pw_bytes(pw: str) -> bytes:
    # bcrypt has a hard 72-byte input limit; truncate defensively.
    return pw.encode("utf-8")[:72]


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(_pw_bytes(pw), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(pw), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """Decode the Bearer token and return the user_id (401 if missing/invalid)."""
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("token has no subject")
        return user_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
