import os
import asyncio
from typing import Optional
from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres import AsyncPostgresStore  # type: ignore[import-not-found]
from langgraph.store.base import BaseStore, IndexConfig
from langchain.embeddings import init_embeddings

_memory_store: Optional[InMemoryStore] = None

_postgres_store: Optional[AsyncPostgresStore] = None
_postgres_store_context: Optional[object] = None
_postgres_store_lock = asyncio.Lock()


async def get_postgres_store() -> AsyncPostgresStore:
    """
    Get or create the global PostgreSQL store instance for long-term memory.
    The store persists memories across threads and sessions for the same user.
    """
    global _postgres_store, _postgres_store_context

    async with _postgres_store_lock:
        if _postgres_store is None:
            db_url = os.getenv("DB_URL") or os.getenv("DB_URL_LOCAL")
            if not db_url:
                raise ValueError("DB_URL or DB_URL_LOCAL environment variable must be set")
            
            # Configure embeddings for semantic search if OpenAI key is available
            index_config = None
            if os.getenv("OPENAI_API_KEY"):
                try:
                    index_config = IndexConfig(
                        embed=init_embeddings("openai:text-embedding-3-small"),
                        dims=1536,
                        fields=["$"],  # Embed all fields
                    )
                except Exception:
                    # If embeddings fail, fall back to non-semantic search
                    pass

            _postgres_store_context = AsyncPostgresStore.from_conn_string(
                db_url,
                index=index_config,
            )
            _postgres_store = await _postgres_store_context.__aenter__()
            await _postgres_store.setup()

    return _postgres_store


async def get_memory_store() -> InMemoryStore:
    """
    Get the global in-memory store instance for long-term memory.
    Use for development/testing. For production, use get_postgres_store().
    
    The store persists memories across threads and sessions for the same user.
    """
    global _memory_store

    if _memory_store is None:
        # Configure embeddings for semantic search if OpenAI key is available
        index_config = None
        if os.getenv("OPENAI_API_KEY"):
            try:
                index_config = IndexConfig(
                    embed=init_embeddings("openai:text-embedding-3-small"),
                    dims=1536,
                    fields=["$"],  # Embed all fields
                )
            except Exception:
                # If embeddings fail, fall back to non-semantic search
                pass

        _memory_store = InMemoryStore(index=index_config)

    return _memory_store


async def get_store(use_postgres: bool = True) -> BaseStore:
    """
    Get the appropriate store backend.
    
    Args:
        use_postgres: If True, use PostgreSQL store (production).
                     If False, use in-memory store (development/testing).
    
    Returns:
        A configured store instance (AsyncPostgresStore or InMemoryStore)
    """
    if use_postgres and (os.getenv("DB_URL") or os.getenv("DB_URL_LOCAL")):
        return await get_postgres_store()
    else:
        return await get_memory_store()
