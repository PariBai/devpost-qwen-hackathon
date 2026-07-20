from typing import Literal
from langgraph.types import Command
from langgraph.runtime import Runtime
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage

from app.common import state
from app.common.state import SessionState
from app.common.context import SessionContext
from app.common.utils import (
    trim_messages,
    _llm_call,
    is_quota_error,
    get_active_qwen_model,
    advance_qwen_model,
)
from app.common.schemas import RouteDecision, PreferenceUpdate
from app.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_TEMPLATE
from app.prompts.synthesize import SYNTHESIZE_SYSTEM_PROMPT, SYNTHESIZE_USER_TEMPLATE
from app.prompts.memory_writer import MEMORY_WRITER_SYSTEM_PROMPT, MEMORY_WRITER_USER_TEMPLATE
from app.agents.compliance_agent import get_compliance_agent
from app.agents.finance_agent import get_finance_agent
from app.common.utils import filter_agent_messages
from app.common import memory as memory_utils
from app.common.retrieval import select_relevant
# from langchain_core.callbacks import UsageMetadataCallbackHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_history(messages, max_msgs: int = 2) -> str:
    prior = messages[:-1][-max_msgs:]
    lines = []
    last_role = None  # track previous role

    for m in prior:
        role = getattr(m, "type", "")
        content = m.content if isinstance(m.content, str) else str(m.content)

        if role == "human" and content.strip():
            lines.append(f"User: {content.strip()}")
            last_role = "human"

        elif role == "ai" and content.strip():
            if last_role == "ai":
                # Replace the previous AI line instead of appending
                lines[-1] = f"Assistant: {content.strip()}"
            else:
                lines.append(f"Assistant: {content.strip()}")
            last_role = "ai"

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

async def init_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["compliance_node", "finance_node","__end__"]]:
    """Router / init node (runs first every turn).

    1. Trims old turns (context management).
    2. Stashes the latest user query.
    3. PRELOADS the user's long-term preferences into context ONCE (the READ path) so
       agents can apply them via the system prompt with no extra tool round-trip.
    4. Makes ONE structured LLM call to classify which specialist(s) are needed, then
       fans out: goto a single agent node, or BOTH (parallel) when the query spans domains.
    The router only picks DOMAINS - the agents themselves resolve entities from the full
    message history, so the router never needs to name a specific broker/company.
    """
    trimmed = trim_messages(state)
    messages_update = trimmed if isinstance(trimmed, list) else trimmed["messages"]

    query = state["messages"][-1].content
    history = _render_history(state["messages"])

    # READ path: fetch the user's preferences once per turn, then RECALL only the ones
    # relevant to this query (always-on constraints + top-K semantic matches) instead of
    # dumping them all. The dynamic_model middleware injects the SELECTED subset into each
    # agent's system prompt, so the prompt stays small and focused as memory grows.
    if runtime.store is not None:
        try:
            prefs = await memory_utils.list_preferences(runtime.store, runtime.context.user_id)
            all_prefs = {p.key: p.value for p in prefs}
            selected, recall_trace = await select_relevant(query, all_prefs)
            runtime.context.user_preferences = selected
            runtime.context.recalled = recall_trace
        except Exception as e:
            # Preferences are an enhancement, not a hard dependency - never fail the
            # turn if the store read hiccups.
            print(f"Warning: failed to preload preferences: {e}")
            runtime.context.user_preferences = {}
            runtime.context.recalled = []

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


async def compliance_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["synthesize_node", "memory_writer_node"]]:
    """Run the PSX compliance agent (SQL over psx.db). Streams its text as 'compliance_chunk'
    and stores the full answer on the context for the synthesize node."""
    writer = get_stream_writer()
    BLOCKED_TOOLS = {
    "list_financials",
    "read_financials",
    "calc",
    "get_stock_snapshot"
    }

    compliance_input_messages = filter_agent_messages(state["messages"], BLOCKED_TOOLS)

    agent = await get_compliance_agent()

    # Stream the agent on the currently-active Qwen model. If it hits a quota error BEFORE
    # any text has streamed, permanently promote the next fallback model and retry. With no
    # fallbacks left this re-raises exactly as before.
    full_content = ""
    agent_messages = []
    while True:
        runtime.context.model = get_active_qwen_model()
        full_content = ""
        agent_messages = []
        try:
            async for stream_mode, chunk in agent.astream(
                {"messages": compliance_input_messages},
                stream_mode = ["updates","messages"],
                context = runtime.context
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
                                if key == "model" and isinstance(msg, AIMessage):
                                    agent_messages.append(msg)
                                elif key == "tools" and isinstance(msg, ToolMessage):
                                    agent_messages.append(msg)
            break
        except Exception as e:
            if is_quota_error(e) and not full_content and advance_qwen_model():
                continue
            raise

    runtime.context.compliance_output = full_content             # only THIS node writes this field
    # print("agent messagwes inside compliance_node", agent_messages)
    # If this is the ONLY agent, skip synthesize (nothing to merge) and go straight to
    # the memory writer. We still route THROUGH memory_writer_node (not __end__) so the
    # preference-reflection step runs on single-agent turns too.
    if len(runtime.context.agents) == 1 and runtime.context.agents[0] == "compliance_node":
        goto = "memory_writer_node"
    else:
        goto = "synthesize_node"
    return Command(goto=goto,
                   update={"messages": agent_messages})
   


async def finance_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["synthesize_node", "memory_writer_node"]]:
    """Run the PSX finance agent (markdown financial summaries). Streams its text as
    'finance_chunk' and stores the full answer on the context for the synthesize node."""
    writer = get_stream_writer()
    BLOCKED_TOOLS = {
   "run_sql"
    }

    finance_input_messages = filter_agent_messages(state["messages"], BLOCKED_TOOLS)
    agent = await get_finance_agent()

    # Stream the agent on the currently-active Qwen model. If it hits a quota error BEFORE
    # any text has streamed, permanently promote the next fallback model and retry. With no
    # fallbacks left this re-raises exactly as before.
    full_content = ""
    agent_messages = []
    while True:
        runtime.context.model = get_active_qwen_model()
        full_content = ""
        agent_messages = []
        try:
            async for stream_mode, chunk in agent.astream(
                {"messages": finance_input_messages},
                stream_mode = ["updates","messages"],
                context = runtime.context
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
                                if key == "model" and isinstance(msg, AIMessage):
                                    agent_messages.append(msg)
                                elif key == "tools" and isinstance(msg, ToolMessage):
                                    agent_messages.append(msg)
            break
        except Exception as e:
            if is_quota_error(e) and not full_content and advance_qwen_model():
                continue
            raise

    runtime.context.finance_output = full_content            # only THIS node writes this field
    # print("agent messagwes inside finance_node", agent_messages)
    # If this is the ONLY agent, skip synthesize and route straight to the memory
    # writer (still THROUGH memory_writer_node, not __end__, so reflection runs).
    if len(runtime.context.agents) == 1 and runtime.context.agents[0] == "finance_node":
        goto = "memory_writer_node"
    else:
        goto = "synthesize_node"

    return Command(goto=goto,
                   update={"messages": agent_messages})


async def synthesize_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["memory_writer_node"]]:
    """Fan-in: runs once after the specialist(s) finish (only reached when 2+ agents ran).

    - Makes one LLM call to merge the specialists' answers into a single unified reply,
      streamed as 'synthesize_chunk'.
    - The merged text is written to `messages` (so future turns have it as context) AND
      onto context.synthesize_output, which memory_writer_node treats as "the final
      answer" for this turn.
    Routes to memory_writer_node so the preference-reflection step runs before END.
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

    # Expose the merged answer so memory_writer_node can reflect on the FINAL text the
    # user saw (not just one specialist's slice). Per-thread messages are persisted by
    # the Postgres checkpointer; the long-term store holds only user preferences.
    runtime.context.synthesize_output = full

    return Command(goto="memory_writer_node", update={"messages": [AIMessage(content=full)]})


async def memory_writer_node(state: SessionState, runtime: Runtime[SessionContext]) -> Command[Literal["__end__"]]:
    """Post-turn reflection (WRITE path). Single exit point for the whole graph.

    Runs AFTER the answer has streamed, so it adds no latency to the user-visible
    response. It looks at the finished turn and reconciles the user's long-term
    preferences:
      1. Resolve the final answer (synthesize output if 2 agents ran, else the one
         agent's output).
      2. Load existing preferences (to reuse keys / know what can be forgotten).
      3. One structured LLM call -> a list of upsert/delete ops (usually empty).
      4. Apply the ops to the store.

    The agent never decides to save anything; this node does. Failures are swallowed so
    a bad memory write can never break a turn the user already got an answer for.
    """
    # No store (e.g. store misconfigured) -> nothing to write, just finish.
    if runtime.store is None:
        return Command(goto="__end__")

    try:
        user_id = runtime.context.user_id

        # (1) Resolve "the final answer" across both graph paths. Priority: the merged
        # synthesize text when 2+ agents ran; otherwise whichever single agent answered.
        final_answer = (
            runtime.context.synthesize_output
            or runtime.context.compliance_output
            or runtime.context.finance_output
        )

        # (2) Current preferences, as {key: value}, so the LLM reuses keys instead of
        # inventing duplicates and knows what exists to forget.
        existing = await memory_utils.list_preferences(runtime.store, user_id)
        existing_view = {item.key: item.value for item in existing}

        # (3) One reflection call. Returns PreferenceUpdate.ops - empty on most turns.
        update = _llm_call(
            system_prompt=MEMORY_WRITER_SYSTEM_PROMPT,
            user_prompt_template=MEMORY_WRITER_USER_TEMPLATE,
            user_prompt_inputs={
                "previous_assistant_answer": final_answer,
                "current_user_query": state.get("user_query", ""),
                "existing_preferences": existing_view,
            },
            llm=runtime.context.model,
            schema=PreferenceUpdate,
            structured_output=True,
        )

        # (4) Apply each op. upsert overwrites the key; delete forgets it. Also record
        # a serializable copy on the context so the API can stream a live memory feed
        # ("🧠 remembered / 🗑 forgot") to the UI.
        applied_ops = []
        for op in getattr(update, "ops", []) or []:
            if op.action == "upsert":
                await memory_utils.save_preference(runtime.store, user_id, op.key, op.value)
                print(f"[memory] remembered '{op.key}': {op.reason}")
            elif op.action == "delete":
                await memory_utils.delete_preference(runtime.store, user_id, op.key)
                print(f"[memory] forgot '{op.key}': {op.reason}")
            else:
                continue
            applied_ops.append(
                {"action": op.action, "key": op.key, "value": op.value, "reason": op.reason}
            )
        runtime.context.memory_ops = applied_ops
    except Exception as e:
        # Never fail the turn on a memory write - the user already has their answer.
        print(f"Warning: memory_writer failed (turn still succeeded): {e}")

    return Command(goto="__end__")
