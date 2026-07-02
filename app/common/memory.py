"""
Cross-session long-term memory: stores ONLY user preferences.

Per-thread / per-session context is persisted separately in Postgres
(the checkpointer), so this module intentionally covers preferences alone.

Preferences are stored under the namespace:
  (user_id, "preferences") -> { preference_key: preference_value }
"""

from typing import List, Dict, Any, Optional
from langgraph.store.base import BaseStore, Item


# ============================================================================
# Namespace
# ============================================================================

def get_user_preferences_namespace(user_id: str) -> tuple:
    """Get the namespace tuple for a user's preferences."""
    return (user_id, "preferences")


# ============================================================================
# Preference Management
# ============================================================================

async def save_preference(
    store: BaseStore,
    user_id: str,
    preference_key: str,
    preference_value: Dict[str, Any],
) -> None:
    """
    Save or update a user preference (aput overwrites an existing key).

    Args:
        store: The LangGraph store instance
        user_id: User identifier
        preference_key: Preference identifier (e.g., "language", "risk_tolerance")
        preference_value: Dictionary containing preference data
    """
    namespace = get_user_preferences_namespace(user_id)
    await store.aput(namespace, preference_key, preference_value)


async def get_preference(
    store: BaseStore,
    user_id: str,
    preference_key: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single user preference.

    Returns:
        The preference data, or None if not found.
    """
    namespace = get_user_preferences_namespace(user_id)
    item = await store.aget(namespace, preference_key)
    return item.value if item else None


async def list_preferences(
    store: BaseStore,
    user_id: str,
    limit: int = 100,
) -> List[Item]:
    """
    List all stored preferences for a user.

    Returns:
        List of Item objects (each item.key is the preference key,
        item.value is the preference data).
    """
    namespace = get_user_preferences_namespace(user_id)
    return await store.asearch(namespace, limit=limit)


async def delete_preference(
    store: BaseStore,
    user_id: str,
    preference_key: str,
) -> None:
    """
    Delete a user preference (used to forget outdated preferences).
    """
    namespace = get_user_preferences_namespace(user_id)
    await store.adelete(namespace, preference_key)
