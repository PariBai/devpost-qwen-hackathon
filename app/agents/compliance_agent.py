from typing import Callable
from langchain.agents import create_agent
from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse
)
from app.prompts.compliance import COMPLIANCE_SYSTEM_PROMPT
from app.common.context import SessionContext
from app.tools.compliance import run_sql

@wrap_model_call
async def dynamic_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    model = request.runtime.context.model
    return await handler(request.override(model=model))

async def get_compliance_agent():
    return create_agent(
        name = "Compliance",
        model = None,
        system_prompt = COMPLIANCE_SYSTEM_PROMPT,
        tools = [
            run_sql,
        ],
        context_schema = SessionContext,
        middleware = [
            dynamic_model,
        ]
    )
