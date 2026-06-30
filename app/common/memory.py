"""
Long-term memory utilities for storing and retrieving cross-session interaction memories.

Memories are organized by user and namespace:
  - (user_id, "memories") -> general facts and preferences
  - (user_id, "compliance") -> compliance-specific learnings
  - (user_id, "finance") -> finance-specific learnings
"""

import uuid
from typing import List, Dict, Any, Optional
from langgraph.store.base import BaseStore, Item


# ============================================================================
# Memory Namespace Constants
# ============================================================================

def get_user_memory_namespace(user_id: str, context: str = "general") -> tuple:
    """
    Get the namespace tuple for a user's memories.
    
    Args:
        user_id: The user identifier
        context: Memory context ("general", "compliance", "finance", etc.)
    
    Returns:
        A namespace tuple like (user_id, "memories", context)
    """
    return (user_id, "memories", context)


def get_user_preferences_namespace(user_id: str) -> tuple:
    """Get namespace for user preferences."""
    return (user_id, "preferences")


def get_user_interaction_namespace(user_id: str) -> tuple:
    """Get namespace for interaction history and patterns."""
    return (user_id, "interactions")


# ============================================================================
# Memory Management Functions
# ============================================================================

async def save_memory(
    store: BaseStore,
    user_id: str,
    memory_content: Dict[str, Any],
    context: str = "general",
) -> str:
    """
    Save a new memory for a user.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        memory_content: Dictionary containing the memory data
        context: Memory context/category
    
    Returns:
        The memory ID (UUID)
    """
    namespace = get_user_memory_namespace(user_id, context)
    memory_id = str(uuid.uuid4())
    await store.aput(namespace, memory_id, memory_content)
    return memory_id


async def save_preference(
    store: BaseStore,
    user_id: str,
    preference_key: str,
    preference_value: Dict[str, Any],
) -> None:
    """
    Save or update a user preference.
    
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
    Retrieve a user preference.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        preference_key: Preference identifier
    
    Returns:
        The preference data, or None if not found
    """
    namespace = get_user_preferences_namespace(user_id)
    item = await store.aget(namespace, preference_key)
    return item.value if item else None


async def search_memories(
    store: BaseStore,
    user_id: str,
    query: Optional[str] = None,
    context: str = "general",
    limit: int = 5,
    filter_dict: Optional[Dict[str, Any]] = None,
) -> List[Item]:
    """
    Search for memories for a user.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        query: Semantic search query (optional)
        context: Memory context/category
        limit: Maximum number of results
        filter_dict: Optional filter for exact matching
    
    Returns:
        List of Item objects containing matching memories
    """
    namespace = get_user_memory_namespace(user_id, context)
    
    # Use semantic search if query is provided, otherwise list all
    memories = await store.asearch(
        namespace,
        query=query,
        filter=filter_dict,
        limit=limit,
    )
    return memories


async def get_memory_by_id(
    store: BaseStore,
    user_id: str,
    memory_id: str,
    context: str = "general",
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific memory by ID.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        memory_id: The memory UUID
        context: Memory context/category
    
    Returns:
        The memory data, or None if not found
    """
    namespace = get_user_memory_namespace(user_id, context)
    item = await store.aget(namespace, memory_id)
    return item.value if item else None


async def delete_memory(
    store: BaseStore,
    user_id: str,
    memory_id: str,
    context: str = "general",
) -> None:
    """
    Delete a specific memory.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        memory_id: The memory UUID
        context: Memory context/category
    """
    namespace = get_user_memory_namespace(user_id, context)
    await store.adelete(namespace, memory_id)


async def update_memory(
    store: BaseStore,
    user_id: str,
    memory_id: str,
    updated_content: Dict[str, Any],
    context: str = "general",
) -> None:
    """
    Update an existing memory.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        memory_id: The memory UUID
        updated_content: Updated memory data
        context: Memory context/category
    """
    namespace = get_user_memory_namespace(user_id, context)
    await store.aput(namespace, memory_id, updated_content)


# ============================================================================
# Interaction History Functions
# ============================================================================

async def log_interaction(
    store: BaseStore,
    user_id: str,
    interaction_type: str,
    data: Dict[str, Any],
) -> str:
    """
    Log an interaction (query, result, etc.) for the user.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        interaction_type: Type of interaction ("query", "result", "clarification", etc.)
        data: Interaction data
    
    Returns:
        The interaction ID
    """
    namespace = get_user_interaction_namespace(user_id)
    interaction_id = str(uuid.uuid4())
    interaction_record = {
        "type": interaction_type,
        "data": data,
    }
    await store.aput(namespace, interaction_id, interaction_record)
    return interaction_id


async def get_recent_interactions(
    store: BaseStore,
    user_id: str,
    limit: int = 10,
) -> List[Item]:
    """
    Get recent interactions for a user.
    
    Args:
        store: The LangGraph store instance
        user_id: User identifier
        limit: Maximum number of interactions to return
    
    Returns:
        List of recent interaction records
    """
    namespace = get_user_interaction_namespace(user_id)
    return await store.asearch(namespace, limit=limit)
