import os
import asyncio
from typing import Optional
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import InMemorySaver

_memory_checkpointer: Optional[InMemorySaver] = None

_postgres_checkpointer: Optional[AsyncPostgresSaver] = None
_postgres_checkpointer_context: Optional[object] = None
_postgres_checkpointer_lock = asyncio.Lock()

async def get_postgres_checkpointer() -> AsyncPostgresSaver:
    """
    Get or create the global checkpointer instance
    """
    global _postgres_checkpointer, _postgres_checkpointer_context

    async with _postgres_checkpointer_lock:
        if _postgres_checkpointer is None:
            _postgres_checkpointer_context = AsyncPostgresSaver.from_conn_string(os.getenv("DB_URL", os.getenv("DB_URL_LOCAL")))
            _postgres_checkpointer = await _postgres_checkpointer_context.__aenter__()
            await _postgres_checkpointer.setup()
    return _postgres_checkpointer

async def get_memory_checkpointer() -> InMemorySaver:
    """
    Get the global in-memory checkpointer instance
    """
    global _memory_checkpointer

    if _memory_checkpointer is None:
        _memory_checkpointer = InMemorySaver()

    return _memory_checkpointer
