"""
FastAPI backend entrypoint for the PSX MemoryAgent.

Kept at the repo root (outside the `app/` package) so `app/` stays pure agent
logic (graph, agents, tools, memory) and this file is just the web/delivery layer.
Run:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Wraps the full LangGraph workflow (router -> compliance/finance -> synthesize ->
memory_writer) behind a streaming /chat endpoint (Server-Sent Events).

- Per-session/thread context  -> Postgres checkpointer (keyed by thread_id)
- Cross-session user memory    -> Postgres store       (keyed by user_id)

Phase 1: user_id is taken from the request body (defaults to "demo-user").
Phase 2 will replace that with a user_id extracted from a JWT login token.
"""

import json
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.common.utils import _get_model
from app.common.context import SessionContext
from app.common.store import get_store
from app.common import memory as memory_utils
from app.graph.compile import get_compiled_agent

load_dotenv()

# The compiled graph is registered under this name in app/graph/compile.py.
AGENT_NAME = "psx_agent"

app = FastAPI(title="PSX MemoryAgent API")

# Token-based auth (Bearer, added in Phase 2), not cookies -> "*" origins are safe.
# Tighten allow_origins to the deployed frontend URL before submission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    # Phase 1 stand-in for auth. Keep it STABLE per user so cross-session memory
    # (preferences) ties back to the same person. Phase 2 derives this from a JWT.
    user_id: str = "demo-user"


def _sse(payload: dict) -> str:
    """Format a dict as one Server-Sent Event frame."""
    return f"data: {json.dumps(payload)}\n\n"


async def stream_agent_response(message: str, thread_id: str, user_id: str):
    """Run the graph and stream its answer chunks as SSE frames."""
    try:
        agent = await get_compiled_agent(AGENT_NAME)

        # Fresh context per request: model + identity. The per-node output fields
        # (compliance_output, ...) auto-reset because we build a new object each turn.
        context = SessionContext(
            thread_id=thread_id,
            user_id=user_id,
            model=_get_model("qwen"),
            agents=None,
        )
        config = {"configurable": {"thread_id": thread_id}}

        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            stream_mode="custom",
            context=context,
            config=config,
        ):
            if not chunk:
                continue

            # Mirror the notebook's routing: show the single specialist's stream when
            # only one agent ran, otherwise show the merged synthesize stream. This
            # avoids dumping raw specialist text AND the merged answer for one query.
            agents = context.agents or []
            if agents == ["compliance_node"]:
                content = chunk.get("compliance_chunk")
            elif agents == ["finance_node"]:
                content = chunk.get("finance_chunk")
            else:
                content = chunk.get("synthesize_chunk")

            if content:
                yield _sse({"type": "text", "content": content})

        # After the turn, push the user's current preferences so the UI's memory
        # panel can refresh live (memory_writer_node may have just changed them).
        try:
            store = await get_store()
            prefs = await memory_utils.list_preferences(store, user_id)
            yield _sse({"type": "preferences", "content": {p.key: p.value for p in prefs}})
        except Exception:
            pass  # memory panel is a nice-to-have; never fail the turn over it

        yield _sse({"type": "end"})

    except Exception as e:
        print(f"Error in /chat: {e}\n{traceback.format_exc()}")
        yield _sse({"type": "error", "content": str(e)})
        yield _sse({"type": "end"})


@app.post("/chat")
async def chat(request: ChatRequest):
    """Stream the agent's answer for one user message (SSE)."""
    return StreamingResponse(
        stream_agent_response(
            message=request.message,
            thread_id=request.thread_id,
            user_id=request.user_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/me/preferences")
async def get_preferences(user_id: str = "demo-user"):
    """Return the user's stored long-term preferences (powers the memory panel)."""
    try:
        store = await get_store()
        prefs = await memory_utils.list_preferences(store, user_id)
        return {"user_id": user_id, "preferences": {p.key: p.value for p in prefs}}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/health")
def health():
    """Liveness probe for the ECS / load balancer."""
    return {"status": "ok", "agent": AGENT_NAME}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)
