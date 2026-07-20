from dataclasses import dataclass
from typing import Optional, Dict, Any, List
# NOTE: `model` is injected at runtime (see app/common/utils.py::_get_model) and
# read by the dynamic_model middleware in each agent. It is a Qwen chat model on the
# Alibaba Cloud DashScope endpoint; typed as Any so the context schema stays
# provider-agnostic.


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

    # The 1-based id of the Q+A row this turn will become, computed by the API BEFORE
    # streaming so the make_graph tool can name chart files deterministically
    # (charts/<user_id>/<chat_id>/<qid>_chartN.png). Set fresh per request.
    qid: Optional[int] = None

    # Chart image URLs produced THIS turn by the make_graph tool (the finance/compliance
    # agents call it when a visual beats text). Each entry is a public path like
    # "/charts/<uid>/<cid>/<qid>_chart1.png". Started as [] per request so a previous
    # turn's charts never leak in; after the answer streams the API persists these on the
    # chat_history row (attachments) and streams an "images" event so the UI renders them.
    images: Optional[List[str]] = None

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

    # Recall trace for THIS turn (the READ path): which stored preferences were
    # considered and which were injected into the prompt, with similarity scores.
    # Surfaced to the UI as a "🔎 recalled N of M memories" chip — the visible proof
    # of relevance-based recall within a limited context. Each item:
    # {"key": str, "score": float|None, "kept": bool, "basis": str}.
    recalled: Optional[List[Dict[str, Any]]] = None
