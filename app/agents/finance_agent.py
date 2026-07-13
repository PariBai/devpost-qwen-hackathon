from typing import Callable
from langchain.agents import create_agent
from langchain.agents.middleware import (
    wrap_model_call,
    ModelRequest,
    ModelResponse,
    ToolCallLimitMiddleware
)
from app.prompts.finance import FINANCE_SYSTEM_PROMPT
from app.common.context import SessionContext
from app.tools.finance import list_financials, read_financials, calc , get_stock_snapshot, list_shariah_compliant
from app.tools.charts import make_graph
from app.tools.memory import (
    get_user_preference,
    save_user_preference,
    delete_user_preference,
)

@wrap_model_call
async def dynamic_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    # Model is injected per-request (provider-agnostic); see SessionContext.
    model = request.runtime.context.model

    # READ path: preferences were preloaded once in init_node. Inject them into the
    # system prompt so the agent applies them with NO extra tool call / round-trip.
    prefs = request.runtime.context.user_preferences or {}
    if prefs:
        pref_lines = "\n".join(f"- {k}: {v}" for k, v in prefs.items())
        system_prompt = (
            f"{request.system_prompt}\n\n"
            f"## Known user preferences (apply these unless the user overrides them)\n"
            f"{pref_lines}"
        )
        return await handler(request.override(model=model, system_prompt=system_prompt))

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
            get_stock_snapshot,
            list_shariah_compliant,
            make_graph,
            get_user_preference,
            save_user_preference,
            delete_user_preference,
        ],
        context_schema = SessionContext,
        middleware = [
            dynamic_model,
            ToolCallLimitMiddleware(
                tool_name = "get_stock_snapshot",
                run_limit = 5,
            ),
        ]
       
    )
