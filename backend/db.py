"""
Async Postgres access for the app's OWN tables: users, chats, chat_history.

This is separate from LangGraph's checkpointer/store (which manage agent context and
long-term memory). It uses the same Postgres server via DB_URL, with its own pool.

Tables:
  users        -> accounts (id, email, full_name, password_hash); login by email
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
        email         TEXT UNIQUE NOT NULL,
        full_name     TEXT,
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
        attachments TEXT NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_history_chat ON chat_history(chat_id, qid)",
]

# Best-effort migrations for a `users` table already deployed with the old
# `username`-based schema. Each runs in its own transaction and is allowed to
# fail (e.g. on a fresh DB where `username` never existed) without aborting startup.
_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT",
    "ALTER TABLE users ALTER COLUMN username DROP NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    # chat_history gained an attachments column (JSON array of chart image URLs) for the
    # make_graph feature; add it to already-deployed databases.
    "ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS attachments TEXT NOT NULL DEFAULT '[]'",
]


async def init_tables() -> None:
    """Create the app tables if they don't exist (idempotent, runs at startup)."""
    pool = await get_pool()
    for stmt in _SCHEMA:
        async with pool.connection() as conn:
            await conn.execute(stmt)
    # Migrations are best-effort: a failure here must not block startup.
    for stmt in _MIGRATIONS:
        try:
            async with pool.connection() as conn:
                await conn.execute(stmt)
        except Exception as e:
            print(f"[db] migration skipped ({stmt.split(' ')[0]}...): {e}")
