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
    email = body.email.strip().lower()
    full_name = body.full_name.strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "a valid email is required")
    if not full_name:
        raise HTTPException(400, "full name is required")
    if len(body.password) < 6:
        raise HTTPException(400, "password must be at least 6 characters")

    pool = await get_pool()
    user_id = str(uuid.uuid4())  # stable cross-session id, minted once here
    try:
        async with pool.connection() as conn:
            await conn.execute(
                "INSERT INTO users (id, email, full_name, password_hash) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, email, full_name, hash_password(body.password)),
            )
    except UniqueViolation:
        raise HTTPException(409, "an account with this email already exists")

    return AuthResponse(
        token=create_token(user_id),
        user_id=user_id,
        email=email,
        full_name=full_name,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    email = body.email.strip().lower()
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, email, full_name, password_hash FROM users WHERE email = %s",
            (email,),
        )
        row = await cur.fetchone()

    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "invalid email or password")

    uid = str(row["id"])
    return AuthResponse(
        token=create_token(uid),
        user_id=uid,
        email=row["email"],
        full_name=row["full_name"],
    )


@router.get("/me")
async def me(user_id: str = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, email, full_name, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "user not found")
    return {
        "user_id": str(row["id"]),
        "email": row["email"],
        "full_name": row["full_name"],
        "created_at": row["created_at"].isoformat(),
    }
