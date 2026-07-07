"""Auth routes: signup, login, and current-user lookup."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import UniqueViolation

from backend.db import get_pool
from backend.schemas import SignupRequest, LoginRequest, AuthResponse
from backend.security import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest):
    username = body.username.strip()
    if len(username) < 3 or len(body.password) < 6:
        raise HTTPException(400, "username must be >=3 chars and password >=6 chars")

    pool = await get_pool()
    user_id = str(uuid.uuid4())  # stable cross-session id, minted once here
    try:
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (%s, %s, %s)",
                (user_id, username, hash_password(body.password)),
            )
    except UniqueViolation:
        raise HTTPException(409, "username already taken")

    return AuthResponse(token=create_token(user_id), user_id=user_id, username=username)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (body.username.strip(),),
        )
        row = await cur.fetchone()

    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "invalid username or password")

    uid = str(row["id"])
    return AuthResponse(token=create_token(uid), user_id=uid, username=row["username"])


@router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = %s", (user_id,)
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "user not found")
    return {
        "user_id": str(row["id"]),
        "username": row["username"],
        "created_at": row["created_at"].isoformat(),
    }
