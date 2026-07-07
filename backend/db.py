"""
Async Postgres access for the app's OWN tables: users, chats, chat_history.

This is separate from LangGraph's checkpointer/store (which manage agent context and
long-term memory). It uses the same Postgres server via DB_URL, with its own pool.

Tables:
  users        -> accounts (id, username, password_hash)
  chats        -> one row per conversation (id == LangGraph thread_id)
  chat_history -> one row per Q+A, ordered by qid, for rendering past chats in the UI
"""

import os
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

_pool: AsyncConnectionPool | None = None


def _db_url() -> str:
    url = os.getenv("DB_URL") or os.getenv("DB_URL_LOCAL")
    if not url:
        raise RuntimeError("DB_URL or DB_URL_LOCAL must be set for the app database")
    return url


async def get_pool() -> AsyncConnectionPool:
    """Lazily open a shared async connection pool (dict rows everywhere)."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=_db_url(),
            min_size=1,
            max_size=5,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        await _pool.open()
    return _pool


# Each statement runs separately (psycopg executes one statement per call).
_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id            UUID PRIMARY KEY,
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chats (
        id         UUID PRIMARY KEY,
        user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title      TEXT NOT NULL DEFAULT 'New Chat',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id, updated_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS chat_history (
        id         UUID PRIMARY KEY,
        chat_id    UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
        user_id    UUID NOT NULL,
        qid        INTEGER NOT NULL,
        question   TEXT NOT NULL,
        answer     TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_history_chat ON chat_history(chat_id, qid)",
]


async def init_tables() -> None:
    """Create the app tables if they don't exist (idempotent, runs at startup)."""
    pool = await get_pool()
    async with pool.connection() as conn:
        for stmt in _SCHEMA:
            await conn.execute(stmt)
