from typing import Literal
from langgraph.types import Command
from langgraph.runtime import Runtime
from app.common.utils import trim_messages
from langgraph.config import get_stream_writer
from app.common.state import SessionState
from app.common.context import SessionContext
from app.agents.compliance_agent import get_compliance_agent
from langchain.messages import AIMessage, ToolMessage
from langchain_core.callbacks import UsageMetadataCallbackHandler

def init_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["compliance_node"]]:
    """
    Initialization Node - first node in the graph. Trims old turns (context
    management) and stashes the latest user query. Routing to other specialists
    (finance, market, ...) will be decided here later.
    """

    trimmed = trim_messages(state)

    if isinstance(trimmed, list):
        messages_update = trimmed

    elif isinstance(trimmed, dict):
        messages_update = trimmed["messages"]

    return Command(
        goto = "compliance_node",
        update = {
            "user_query": state["messages"][-1].content,
            "messages": messages_update,
        }
    )

async def compliance_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["__end__"]]:
    """
    Compliance Node - runs the PSX compliance agent (SQL over psx.db) and
    streams its text chunks to the frontend writer.
    """

    full_content = ""
    writer = get_stream_writer()
    compliance_agent = await get_compliance_agent()

    skip_json_blob = False
    agent_messages = []
    callback = UsageMetadataCallbackHandler()
    async for stream_mode, chunk in compliance_agent.astream(
        {"messages": state["messages"]},
        stream_mode = ["updates", "messages"],
        context = runtime.context,
        config={"callbacks": [callback]}
    ):
        if stream_mode == "messages":
            message_chunk, metadata = chunk

            if message_chunk.content and metadata.get('langgraph_node') == 'model':
                content = message_chunk.content
                # Qwen / OpenAI-compatible models stream a plain string;
                # Gemini / Anthropic stream a list of typed blocks
                # [{"type": "text", "text": ...}]. Handle both.
                if isinstance(content, str):
                    text = content
                elif (isinstance(content, list) and content
                      and isinstance(content[0], dict)
                      and content[0].get("type") == "text"):
                    text = content[0].get("text", "")
                else:
                    text = ""

                if text:
                    if text.startswith('{') or text.startswith('<'):
                        skip_json_blob = True
                    if skip_json_blob:
                        if text.endswith('}') or text.endswith('>'):
                            skip_json_blob = False
                        continue
                    writer({"compliance_chunk": text})
                    full_content += text

        if stream_mode == "updates":
            for key in ["model", "tools"]:
                if key in chunk and chunk[key].get("messages"):
                    for msg in chunk[key]["messages"]:
                        if key == "model" and isinstance(msg, AIMessage):
                            agent_messages.append(msg)
                        elif key == "tools" and isinstance(msg, ToolMessage):
                            agent_messages.append(msg)

    runtime.context.usage = callback.usage_metadata

    return Command(
        goto = "__end__",
        update = {
            "messages": agent_messages,
        }
    )
