from typing import Literal
from langgraph.types import Command
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from app.common.state import SessionState
from app.common.context import SessionContext
from app.common.utils import trim_messages, _llm_call
from app.common.schemas import RouteDecision
from app.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_TEMPLATE
from app.prompts.synthesize import SYNTHESIZE_SYSTEM_PROMPT, SYNTHESIZE_USER_TEMPLATE
from app.agents.compliance_agent import get_compliance_agent
from app.agents.finance_agent import get_finance_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_history(messages, max_msgs: int = 8) -> str:
    """Render the recent conversation (excluding the latest message) as plain text
    for the router, so it can resolve references like 'this broker' / 'that company'.
    Only user/assistant text is included - tool calls and system messages are skipped."""
    prior = messages[:-1][-max_msgs:]          # everything before the latest message
    lines = []
    for m in prior:
        role = getattr(m, "type", "")
        content = m.content if isinstance(m.content, str) else str(m.content)
        if role == "human" and content.strip():
            lines.append(f"User: {content.strip()}")
        elif role == "ai" and content.strip():
            lines.append(f"Assistant: {content.strip()}")
    return "\n".join(lines) if lines else "(no prior conversation)"


async def _stream_agent(agent, messages, runtime, chunk_key: str) -> str:
    """Run a specialist sub-agent and stream its visible text to the frontend under
    `chunk_key`. Returns the full accumulated answer text (which the caller stores on
    the context for the synthesize node). Handles both Qwen/OpenAI (plain-string content)
    and Gemini/Anthropic (list-of-blocks content)."""
    writer = get_stream_writer()
    full_content = ""
    skip_json_blob = False

    async for stream_mode, chunk in agent.astream(
        {"messages": messages},
        stream_mode=["messages"],
        context=runtime.context,
    ):
        if stream_mode != "messages":
            continue
        message_chunk, metadata = chunk
        if not (message_chunk.content and metadata.get("langgraph_node") == "model"):
            continue

        content = message_chunk.content
        if isinstance(content, str):                       # Qwen / OpenAI-compatible
            text = content
        elif (isinstance(content, list) and content        # Gemini / Anthropic blocks
              and isinstance(content[0], dict)
              and content[0].get("type") == "text"):
            text = content[0].get("text", "")
        else:
            text = ""

        if text:
            # skip a leading JSON/XML blob some models emit before prose
            if text.startswith("{") or text.startswith("<"):
                skip_json_blob = True
            if skip_json_blob:
                if text.endswith("}") or text.endswith(">"):
                    skip_json_blob = False
                continue
            writer({chunk_key: text})
            full_content += text

    return full_content


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def init_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["compliance_node", "finance_node"]]:
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
        agents = ["compliance", "finance"]

    goto = [f"{a}_node" for a in agents]

    return Command(
        goto=goto,
        update={"user_query": query, "messages": messages_update},
    )


async def compliance_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["synthesize_node"]]:
    """Run the PSX compliance agent (SQL over psx.db). Streams its text as 'compliance_chunk'
    and stores the full answer on the context for the synthesize node."""
    agent = await get_compliance_agent()
    text = await _stream_agent(agent, state["messages"], runtime, "compliance_chunk")
    runtime.context.compliance_output = text          # only THIS node writes this field
    return Command(goto="synthesize_node")


async def finance_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["synthesize_node"]]:
    """Run the PSX finance agent (markdown financial summaries). Streams its text as
    'finance_chunk' and stores the full answer on the context for the synthesize node."""
    agent = await get_finance_agent()
    text = await _stream_agent(agent, state["messages"], runtime, "finance_chunk")
    runtime.context.finance_output = text             # only THIS node writes this field
    return Command(goto="synthesize_node")


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

    # Single (or zero) specialist -> no merge needed.
    if len(outputs) <= 1:
        final = outputs[0][1] if outputs else "Sorry, I couldn't produce an answer for that."
        return Command(goto="__end__", update={"messages": [AIMessage(content=final)]})

    # Two or more specialists -> merge into one answer, streaming the result.
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
