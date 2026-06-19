from typing import Callable
from langchain.agents import create_agent
from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse
)
from app.prompts.finance import FINANCE_SYSTEM_PROMPT
from app.common.context import SessionContext
from app.tools.finance import list_financials, read_financials, calc

@wrap_model_call
async def dynamic_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    model = request.runtime.context.model
    return await handler(request.override(model=model))

async def get_finance_agent():
    return create_agent(
        name = "PSX-Finance",
        model = None,
        system_prompt = FINANCE_SYSTEM_PROMPT,
        tools = [
            list_financials,
            read_financials,
            calc,
        ],
        context_schema = SessionContext,
        middleware = [
            dynamic_model,
        ]
    )
