import os
from typing import Dict, Any
from app.graph.workflows import _create_psx_workflow
from app.common.checkpointer import get_memory_checkpointer, get_postgres_checkpointer
from app.common.store import get_store

_compiled_agents: Dict[str, Any] = {}

# The full PSX due-diligence graph (router -> compliance/finance -> synthesize).
_WORKFLOW_FACTORIES = {
    "psx_agent": _create_psx_workflow()
}

async def get_compiled_agent(agent_name: str, use_postgres: bool = True):
    global _compiled_agents

    if agent_name not in _compiled_agents:

        if agent_name not in _WORKFLOW_FACTORIES:
            raise ValueError(f"Unknown agent: {agent_name}")

        workflow = _WORKFLOW_FACTORIES[agent_name]

        # Use Postgres for BOTH the per-session checkpointer and the cross-session
        # store when a DB URL is configured (production / local Docker); otherwise
        # fall back to in-memory (quick local runs, no Postgres needed).
        use_pg = use_postgres and bool(os.getenv("DB_URL") or os.getenv("DB_URL_LOCAL"))
        checkpointer = await get_postgres_checkpointer() if use_pg else await get_memory_checkpointer()
        store = await get_store(use_postgres=use_pg)
        _compiled_agents[agent_name] = workflow.compile(
            checkpointer=checkpointer,
            store=store,
        )

    return _compiled_agents[agent_name]
