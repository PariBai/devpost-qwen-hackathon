from dataclasses import dataclass
from typing import Optional, Dict, Any

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
