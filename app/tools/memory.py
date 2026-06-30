"""
Memory management tools for storing and retrieving cross-session interaction memories.
These tools enable agents to leverage past interactions and learned information.
"""

from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from app.common.context import SessionContext
from app.common import memory as memory_utils


@tool
async def save_interaction_memory(
    memory_content: Dict[str, Any],
    context_type: str = "general",
    runtime: Optional[ToolRuntime[SessionContext]] = None,
) -> str:
    """
    Save a cross-session memory about an interaction or learning.
    
    Use this to store important facts, preferences, or patterns that should
    be remembered across multiple sessions for the same user.
    
    Args:
        memory_content: Dictionary with keys like 'summary', 'key_findings', 'context'
        context_type: Category of memory (e.g., 'general', 'compliance', 'finance')
        runtime: Injected by LangGraph - contains store and user context
    
    Returns:
        Memory ID for future reference
    """
    if runtime is None or runtime.store is None:
        return "Error: No store available"
    
    user_id = runtime.context.user_id
    memory_id = await memory_utils.save_memory(
        runtime.store,
        user_id,
        memory_content,
        context=context_type,
    )
    return f"Memory saved with ID: {memory_id}"


@tool
async def search_interaction_memories(
    query: str,
    context_type: str = "general",
    limit: int = 5,
    runtime: Optional[ToolRuntime[SessionContext]] = None,
) -> str:
    """
    Search for relevant memories from past interactions.
    
    This performs a semantic search across memories for the current user,
    enabling the agent to recall relevant information from previous sessions.
    
    Args:
        query: Natural language query to search memories (e.g., "user's risk tolerance")
        context_type: Category of memory to search in
        limit: Maximum number of memories to return
        runtime: Injected by LangGraph - contains store and user context
    
    Returns:
        Formatted string containing relevant memories
    """
    if runtime is None or runtime.store is None:
        return "Error: No store available"
    
    user_id = runtime.context.user_id
    memories = await memory_utils.search_memories(
        runtime.store,
        user_id,
        query=query,
        context=context_type,
        limit=limit,
    )
    
    if not memories:
        return f"No memories found for query: {query}"
    
    # Format memories for display
    result_lines = [f"Found {len(memories)} relevant memories:"]
    for i, memory in enumerate(memories, 1):
        result_lines.append(f"\n{i}. {memory.value}")
    
    return "\n".join(result_lines)


@tool
async def get_user_preference(
    preference_key: str,
    runtime: Optional[ToolRuntime[SessionContext]] = None,
) -> str:
    """
    Retrieve a stored user preference.
    
    Args:
        preference_key: The preference identifier (e.g., 'language', 'risk_tolerance')
        runtime: Injected by LangGraph - contains store and user context
    
    Returns:
        The preference value, or a message if not found
    """
    if runtime is None or runtime.store is None:
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
    runtime: Optional[ToolRuntime[SessionContext]] = None,
) -> str:
    """
    Save or update a user preference that persists across sessions.
    
    Use this to record user settings, preferences, or constraints
    that should be remembered for future interactions.
    
    Args:
        preference_key: Preference identifier (e.g., 'language', 'risk_tolerance')
        preference_value: Dictionary containing the preference data
        runtime: Injected by LangGraph - contains store and user context
    
    Returns:
        Confirmation message
    """
    if runtime is None or runtime.store is None:
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
async def log_user_interaction(
    interaction_type: str,
    interaction_data: Dict[str, Any],
    runtime: Optional[ToolRuntime[SessionContext]] = None,
) -> str:
    """
    Log an interaction event for the user's history.
    
    This creates a timestamped record of interactions for later analysis
    and pattern recognition.
    
    Args:
        interaction_type: Type of interaction ('query', 'result', 'clarification', etc.)
        interaction_data: Dictionary with interaction details
        runtime: Injected by LangGraph - contains store and user context
    
    Returns:
        Confirmation message with interaction ID
    """
    if runtime is None or runtime.store is None:
        return "Error: No store available"
    
    user_id = runtime.context.user_id
    interaction_id = await memory_utils.log_interaction(
        runtime.store,
        user_id,
        interaction_type,
        interaction_data,
    )
    return f"Interaction logged with ID: {interaction_id}"


@tool
async def get_recent_interaction_history(
    limit: int = 10,
    runtime: Optional[ToolRuntime[SessionContext]] = None,
) -> str:
    """
    Retrieve the user's recent interaction history.
    
    Args:
        limit: Number of recent interactions to retrieve
        runtime: Injected by LangGraph - contains store and user context
    
    Returns:
        Formatted string containing recent interactions
    """
    if runtime is None or runtime.store is None:
        return "Error: No store available"
    
    user_id = runtime.context.user_id
    interactions = await memory_utils.get_recent_interactions(
        runtime.store,
        user_id,
        limit=limit,
    )
    
    if not interactions:
        return "No interaction history found"
    
    # Format interactions for display
    result_lines = [f"Recent interactions (last {len(interactions)}):"]
    for i, interaction in enumerate(interactions, 1):
        result_lines.append(f"\n{i}. {interaction.value}")
    
    return "\n".join(result_lines)
