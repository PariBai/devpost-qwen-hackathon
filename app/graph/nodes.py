from typing import Literal
from langgraph.types import Command
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage

from app.common import state
from app.common.state import SessionState
from app.common.context import SessionContext
from app.common.utils import trim_messages, _llm_call
from app.common.schemas import RouteDecision
from app.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_TEMPLATE
from app.prompts.synthesize import SYNTHESIZE_SYSTEM_PROMPT, SYNTHESIZE_USER_TEMPLATE
from app.agents.compliance_agent import get_compliance_agent
from app.agents.finance_agent import get_finance_agent
from app.common.utils import filter_agent_messages
# from langchain_core.callbacks import UsageMetadataCallbackHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_history(messages, max_msgs: int = 3) -> str:
    """Render the recent conversation (excluding the latest message) as plain text
    for the router, so it can resolve references like 'this broker' / 'that company'.
    Only user/assistant text is included - tool calls and system messages are skipped."""
    prior = messages[:-1][-max_msgs:]          # everything before the latest message
    lines = []
    for m in prior:
        role = getattr(m, "type", "")
        content = m.content if isinstance(m.content, str) else str(m.content)
        print(f"role: {role}, content: {content}")
        if role == "human" and content.strip():
            lines.append(f"User: {content.strip()}")
        elif role == "ai" and content.strip():
            lines.append(f"Assistant: {content.strip()}")
    return "\n".join(lines) if lines else "(no prior conversation)"


def _extract_text(content) -> str:
    """Normalize message content into plain text across model providers.

    OpenAI/ChatGPT return ``content`` as a plain string, while Gemini and
    Anthropic return a list of content blocks. This handles both so the
    nodes work regardless of which model an agent is configured with.
    """
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)





# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def init_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["compliance_node", "finance_node","__end__"]]:
    """Router / init node (runs first every turn).

    1. Trims old turns (context management).
    2. Stashes the latest user query.
    3. Makes ONE structured LLM call to classify which specialist(s) are needed, then
       fans out: goto a single agent node, or BOTH (parallel) when the query spans domains.
    The router only picks DOMAINS - the agents themselves resolve entities from the full
    message history, so the router never needs to name a specific broker/company.
    """
    trimmed = trim_messages(state)
    messages_update = trimmed if isinstance(trimmed, list) else trimmed["messages"]

    query = state["messages"][-1].content
    history = _render_history(state["messages"])

    decision = _llm_call(
        system_prompt=ROUTER_SYSTEM_PROMPT,
        user_prompt_template=ROUTER_USER_TEMPLATE,
        user_prompt_inputs={"history": history, "query": query},
        llm=runtime.context.model,
        schema=RouteDecision,
        structured_output=True,
    )

    # Fallback: if the structured call failed/returned nothing, run BOTH agents so we
    # never silently drop the user's question (synthesize will merge whatever answers).
    if decision and getattr(decision, "agents", None):
        agents = list(dict.fromkeys(decision.agents))      # de-dup, preserve order
    else:
        agents = ["compliance_node", "finance_node"]
    
    runtime.context.agents = agents  # for tracing/debugging: which agents were chosen this turn

    

    return Command(
        goto=agents,
        update={"user_query": query, "messages": messages_update},
    )


async def compliance_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["synthesize_node", "__end__"]]:
    """Run the PSX compliance agent (SQL over psx.db). Streams its text as 'compliance_chunk'
    and stores the full answer on the context for the synthesize node."""
    writer = get_stream_writer()
    full_content = ""
    BLOCKED_TOOLS = {
    "list_financials",
    "read_financials",
    "calc",
    }

    compliance_input_messages = filter_agent_messages(state["messages"], BLOCKED_TOOLS)
    # compliance_input_messages = state["messages"]

    agent = await get_compliance_agent()
    agent_messages = []
    # callback = UsageMetadataCallbackHandler()
    # print("compliance input messages", compliance_input_messages)
    async for stream_mode, chunk in agent.astream(
        {"messages": compliance_input_messages},
        stream_mode = ["updates","messages"],
        context = runtime.context
        # config={"callbacks": [callback]}
    ):
        if stream_mode == "messages":
            message_chunk, metadata = chunk
            if message_chunk.content and metadata.get('langgraph_node') == 'model':
                text = _extract_text(message_chunk.content)
                writer({"compliance_chunk": text})
                full_content += text
                
        if stream_mode == "updates":
           
            for key in ["model", "tools"]:
                if key in chunk and chunk[key].get("messages"):
                    for msg in chunk[key]["messages"]:
                        # Determine message type
                        if key == "model" and isinstance(msg, AIMessage):
                            agent_messages.append(msg)
                        elif key == "tools" and isinstance(msg, ToolMessage):
                            # ToolMessage
                            agent_messages.append(msg)
    
   
    runtime.context.compliance_output = full_content             # only THIS node writes this field  
    # print("agent messagwes inside compliance_node", agent_messages)
    # if agents length is 1, then we can skip synthesize node and go to __end__
    if len(runtime.context.agents) == 1 and runtime.context.agents[0] == "compliance_node":
        goto = "__end__"
    else:
        goto = "synthesize_node"
    return Command(goto=goto,
                   update={"messages": agent_messages})
   


async def finance_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["synthesize_node", "__end__"]]:
    """Run the PSX finance agent (markdown financial summaries). Streams its text as
    'finance_chunk' and stores the full answer on the context for the synthesize node."""
    writer = get_stream_writer()
    full_content = ""
    BLOCKED_TOOLS = {
   "run_sql"
    }

    finance_input_messages = filter_agent_messages(state["messages"], BLOCKED_TOOLS)
    #   finance_input_messages = state["messages"]
    agent = await get_finance_agent()
    agent_messages = []
    # callback = UsageMetadataCallbackHandler()
   # print("finance input messages", finance_input_messages)
    async for stream_mode, chunk in agent.astream(
        {"messages": finance_input_messages},
        stream_mode = ["updates","messages"],
        context = runtime.context
        # config={"callbacks": [callback]}
    ):
        if stream_mode == "messages":
            message_chunk, metadata = chunk
            if message_chunk.content and metadata.get('langgraph_node') == 'model':
                text = _extract_text(message_chunk.content)
                writer({"finance_chunk": text})
                full_content += text
                
        if stream_mode == "updates":
           
            for key in ["model", "tools"]:
                if key in chunk and chunk[key].get("messages"):
                    for msg in chunk[key]["messages"]:
                        # Determine message type
                        if key == "model" and isinstance(msg, AIMessage):
                            agent_messages.append(msg)
                        elif key == "tools" and isinstance(msg, ToolMessage):
                            # ToolMessage
                            agent_messages.append(msg)

    runtime.context.finance_output = full_content            # only THIS node writes this field
    # print("agent messagwes inside finance_node", agent_messages)
    # if agents length is 1, then we can skip synthesize node and go to __end__
    if len(runtime.context.agents) == 1 and runtime.context.agents[0] == "finance_node":
        goto = "__end__"
    else:
        goto = "synthesize_node"        

    return Command(goto=goto,
                   update={"messages": agent_messages})


async def synthesize_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["__end__"]]:
    """Fan-in: runs once after the specialist(s) finish.

    - If only ONE agent answered: use its text directly (it already streamed live) - no
      extra LLM call.
    - If TWO+ agents answered: make one LLM call to merge them into a single unified
      answer, streamed as 'synthesize_chunk'.
    Either way, the final answer is written to `messages` so future turns have it as context.
    """
    writer = get_stream_writer()

    outputs = [
        (name, txt.strip())
        for name, txt in (
            ("compliance", runtime.context.compliance_output),
            ("finance", runtime.context.finance_output),
        )
        if txt and txt.strip()
    ]

   
    

    # Two or more specialists -> merge into one answer, streaming the result.
    # the findings should be like agent_name + "\n" + agent_answer, separated by two newlines

    findings = "\n\n".join(f"[{name}]\n{txt}" for name, txt in outputs)
    user_prompt = SYNTHESIZE_USER_TEMPLATE.format(query=state["user_query"], findings=findings)
    llm_messages = [
        SystemMessage(content=SYNTHESIZE_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    full = ""
    async for chunk in runtime.context.model.astream(llm_messages):
        content = chunk.content
        if isinstance(content, str):
            text = content
        elif (isinstance(content, list) and content
              and isinstance(content[0], dict)
              and content[0].get("type") == "text"):
            text = content[0].get("text", "")
        else:
            text = ""
        if text:
            writer({"synthesize_chunk": text})
            full += text

    return Command(goto="__end__", update={"messages": [AIMessage(content=full)]})
