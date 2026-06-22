from typing import Dict, Any
from app.graph.workflows import _create_psx_workflow
from app.common.checkpointer import get_memory_checkpointer

_compiled_agents: Dict[str, Any] = {}

# The full PSX due-diligence graph (router -> compliance/finance -> synthesize).
_WORKFLOW_FACTORIES = {
    "psx_agent": _create_psx_workflow()
}

async def get_compiled_agent(agent_name: str):
    global _compiled_agents

    if agent_name not in _compiled_agents:

        if agent_name not in _WORKFLOW_FACTORIES:
            raise ValueError(f"Unknown agent: {agent_name}")

        workflow = _WORKFLOW_FACTORIES[agent_name]
        checkpointer = await get_memory_checkpointer()
        _compiled_agents[agent_name] = workflow.compile(checkpointer = checkpointer)

    return _compiled_agents[agent_name]
