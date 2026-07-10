from dataclasses import dataclass
from typing import Optional, Dict, Any, List
# NOTE: `model` is injected at runtime (see app/common/utils.py::_get_model) and
# read by the dynamic_model middleware in each agent. It is typed as Any so this
# module stays provider-agnostic -- we will swap Gemini -> Qwen/DashScope later
# without touching the context schema.


@dataclass
class SessionContext:
    """
    Context schema for managing session-specific data across agent conversations
    (compliance, finance, ...). Carries the per-request model, usage metadata,
    and cross-session memory access.
    """
    thread_id: str
    user_id: str  # Used for namespacing memories across sessions
    model: Any
    usage: Optional[Dict[str, Any]] = None
    agents : List[str] = None  # List of agents invoked for this session (for tracing/debugging)

    # User's long-term preferences, PRELOADED once per turn in init_node (one store
    # read) and injected into each agent's system prompt by the dynamic_model
    # middleware. This is the READ path: agents apply preferences with no extra tool
    # call / round-trip. Shape: {preference_key: preference_value_dict}.
    user_preferences: Optional[Dict[str, Any]] = None

    # Per-agent final answers for the current turn. Each specialist node writes ONLY
    # its own field (compliance_node -> compliance_output, finance_node -> finance_output),
    # so parallel writes never touch the same attribute -> no race. The synthesize node
    # reads whichever are non-empty. Build a fresh SessionContext per request with these
    # set to "" so they auto-reset every message (no manual clearing needed).
    compliance_output: str = ""
    finance_output: str = ""

    # The merged answer produced by synthesize_node (only set when 2+ agents ran).
    # memory_writer_node prefers this as "the final answer"; on a single-agent turn
    # it stays "" and the writer falls back to the one non-empty agent output.
    synthesize_output: str = ""

    # Preference changes applied THIS turn by memory_writer_node (the WRITE path),
    # surfaced to the UI as the live "🧠 remembered / 🗑 forgot" feed. Each item:
    # {"action": "upsert"|"delete", "key": str, "value": dict, "reason": str}.
    # Left as a fresh [] per request; usually empty (most turns store nothing).
    memory_ops: Optional[List[Dict[str, Any]]] = None
