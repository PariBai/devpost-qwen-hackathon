from typing import Dict, Any
from app.graph.workflows import _create_compliance_workflow
from app.common.checkpointer import get_memory_checkpointer

_compiled_agents: Dict[str, Any] = {}

_WORKFLOW_FACTORIES = {
    "compliance_agent": _create_compliance_workflow()
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
