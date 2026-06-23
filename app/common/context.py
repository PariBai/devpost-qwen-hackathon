from dataclasses import dataclass
from typing import Optional, Dict, Any, list
# NOTE: `model` is injected at runtime (see app/common/utils.py::_get_model) and
# read by the dynamic_model middleware in each agent. It is typed as Any so this
# module stays provider-agnostic -- we will swap Gemini -> Qwen/DashScope later
# without touching the context schema.


@dataclass
class SessionContext:
    """
    Context schema for managing session-specific data across agent conversations
    (compliance, finance, ...). Carries the per-request model and usage metadata.
    """
    thread_id: str
    model: Any
    usage: Optional[Dict[str, Any]] = None
    agents : list = None  # List of agents invoked for this session (for tracing/debugging)

    # Per-agent final answers for the current turn. Each specialist node writes ONLY
    # its own field (compliance_node -> compliance_output, finance_node -> finance_output),
    # so parallel writes never touch the same attribute -> no race. The synthesize node
    # reads whichever are non-empty. Build a fresh SessionContext per request with these
    # set to "" so they auto-reset every message (no manual clearing needed).
    compliance_output: str = ""
    finance_output: str = ""
