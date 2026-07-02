"""
Preference tools: read/write user preferences in the cross-session store.

Per-thread / session context lives in Postgres (the checkpointer); the
long-term store holds user preferences only.
"""

from typing import Dict, Any
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from app.common.context import SessionContext
from app.common import memory as memory_utils


@tool
async def get_user_preference(
    preference_key: str,
    runtime: ToolRuntime[SessionContext],
) -> str:
    """
    Retrieve a stored user preference.

    Args:
        preference_key: The preference identifier (e.g., 'language', 'risk_tolerance')
        runtime: Auto-injected by LangGraph - contains store and user context. Must be a
            BARE `ToolRuntime` annotation (no Optional / no default) or it leaks into the
            tool's JSON schema and breaks bind_tools.

    Returns:
        The preference value, or a message if not found
    """
    if runtime.store is None:
        return "Error: No store available"

    user_id = runtime.context.user_id
    preference = await memory_utils.get_preference(
        runtime.store,
        user_id,
        preference_key,
    )

    if preference:
        return f"User {preference_key}: {preference}"
    else:
        return f"No {preference_key} preference found for this user"


@tool
async def save_user_preference(
    preference_key: str,
    preference_value: Dict[str, Any],
    runtime: ToolRuntime[SessionContext],
) -> str:
    """
    Save or update a user preference that persists across sessions.

    Use this to record user settings, preferences, or constraints
    that should be remembered for future interactions.

    Args:
        preference_key: Preference identifier (e.g., 'language', 'risk_tolerance')
        preference_value: Dictionary containing the preference data
        runtime: Auto-injected by LangGraph - contains store and user context. Keep it a
            BARE `ToolRuntime` annotation (no Optional / no default).

    Returns:
        Confirmation message
    """
    if runtime.store is None:
        return "Error: No store available"

    user_id = runtime.context.user_id
    await memory_utils.save_preference(
        runtime.store,
        user_id,
        preference_key,
        preference_value,
    )
    return f"Preference '{preference_key}' saved successfully"


@tool
async def delete_user_preference(
    preference_key: str,
    runtime: ToolRuntime[SessionContext],
) -> str:
    """
    Delete a stored user preference.

    Use this to forget an outdated or no-longer-valid preference, e.g. when
    the user changes their mind or explicitly asks to remove a setting.

    Args:
        preference_key: Preference identifier to delete (e.g., 'risk_tolerance')
        runtime: Auto-injected by LangGraph - contains store and user context. Keep it a
            BARE `ToolRuntime` annotation (no Optional / no default).

    Returns:
        Confirmation message
    """
    if runtime.store is None:
        return "Error: No store available"

    user_id = runtime.context.user_id

    # Only delete (and confirm) if it actually exists, so the agent gets
    # honest feedback instead of a false "deleted" on a missing key.
    existing = await memory_utils.get_preference(
        runtime.store,
        user_id,
        preference_key,
    )
    if existing is None:
        return f"No '{preference_key}' preference found to delete"

    await memory_utils.delete_preference(
        runtime.store,
        user_id,
        preference_key,
    )
    return f"Preference '{preference_key}' deleted successfully"
