# Cross-Session Interaction Memory Implementation

This document describes the long-term memory system for cross-session interactions in your LangChain/LangGraph agents.

## Overview

The cross-session memory system enables your agents to:
- **Store and recall information** across different sessions for the same user
- **Learn from past interactions** and apply that knowledge to future conversations
- **Maintain user preferences** and constraints across sessions
- **Search memories semantically** using natural language queries

Unlike short-term memory (which is scoped to a single thread), long-term memories persist across threads and can be accessed by any agent for the same user.

## Architecture

### Components

1. **Store (`app/common/store.py`)**
   - Manages persistent storage backend (PostgreSQL or in-memory)
   - Supports semantic search with embeddings (optional)
   - Singleton pattern for efficient resource management

2. **Memory Utilities (`app/common/memory.py`)**
   - Core functions for saving, retrieving, and searching memories
   - Handles namespace organization for different memory types
   - Provides interaction logging

3. **Memory Tools (`app/tools/memory.py`)**
   - LangChain tools that agents can invoke
   - Allows agents to explicitly manage memories
   - Tools are added to both compliance and finance agents

4. **Updated Components**
   - `SessionContext`: Now includes `user_id` for memory namespacing
   - `compile.py`: Passes store to compiled graph
   - Agents: Include memory tools in their tool list
   - `synthesize_node`: Automatically saves interactions to memory

### Memory Namespaces

Memories are organized hierarchically:

```
(user_id, "memories", context_type) -> General memories
(user_id, "preferences") -> User preferences
(user_id, "interactions") -> Interaction history
```

Example namespaces:
- `("user_123", "memories", "general")` - General cross-session learnings
- `("user_123", "memories", "compliance")` - Compliance-specific findings
- `("user_123", "memories", "finance")` - Finance-specific findings
- `("user_123", "preferences")` - User settings/preferences
- `("user_123", "interactions")` - History of interactions

## Usage Examples

### 1. Basic Setup

When invoking the graph, provide `user_id` in the context:

```python
from app.common.context import SessionContext
from app.graph.compile import get_compiled_agent

# Get the compiled agent
agent = await get_compiled_agent("psx_agent", use_postgres=True)

# Create context with user_id
context = SessionContext(
    thread_id="thread_123",
    user_id="user_456",  # Important: provide user_id for memory
    model=your_model,
)

# Invoke the agent
config = {"configurable": {"thread_id": "thread_123"}}
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config=config,
    context=context,
)
```

### 2. Agents Automatically Save Memories

The synthesize node automatically saves:
- Query-response pairs
- Key findings from specialist agents
- Interaction history

This happens automatically without any code changes needed.

### 3. Agent-Invoked Memory Tools

Agents can explicitly use memory tools:

#### Save an Interaction Memory
```
Agent: "I should remember this compliance finding for future reference."
[Uses save_interaction_memory tool]
Memory saved with ID: 12345-abcde
```

#### Search Previous Memories
```
Agent: "Let me search for previous findings about this company's compliance status."
[Uses search_interaction_memories tool]
Found 3 relevant memories:
1. Company XYZ had regulatory issues in Q3 2023
2. Recent audit showed compliance improvements
...
```

#### Store User Preferences
```
Agent: "The user prefers conservative investment strategies."
[Uses save_user_preference tool]
Preference 'investment_style' saved successfully
```

#### Retrieve User Preferences
```
Agent: "Let me check the user's investment preferences."
[Uses get_user_preference tool]
User investment_style: {"risk_tolerance": "conservative", ...}
```

### 4. Manual Memory Management

You can also manage memories programmatically:

```python
from app.common import memory as memory_utils
from app.common.store import get_store

# Get the store
store = await get_store(use_postgres=True)
user_id = "user_456"

# Save a memory
memory_id = await memory_utils.save_memory(
    store,
    user_id,
    {
        "summary": "Company ABC has strong financial position",
        "key_metrics": {"debt_ratio": 0.3, "revenue_growth": 15},
    },
    context="finance"
)

# Search memories
memories = await memory_utils.search_memories(
    store,
    user_id,
    query="company financial strength",
    context="finance",
    limit=5
)

# Log interaction
interaction_id = await memory_utils.log_interaction(
    store,
    user_id,
    "query_response",
    {
        "query": "What's ABC's financial status?",
        "result": "Strong position with low debt",
    }
)
```

## Configuration

### Environment Variables

```bash
# Database configuration (for persistent store)
DB_URL=postgresql://user:password@localhost:5432/memories
DB_URL_LOCAL=postgresql://user:password@localhost:5432/memories

# Optional: Enable semantic search with embeddings
OPENAI_API_KEY=sk-...
```

### Store Backend Selection

- **Development/Testing**: Uses InMemoryStore by default
- **Production**: Use PostgreSQL with `use_postgres=True`

```python
# Development
store = await get_store(use_postgres=False)  # InMemoryStore

# Production
store = await get_store(use_postgres=True)   # PostgreSQL
```

## Memory Lifecycle

1. **Creation**
   - Memories are created when agents use memory tools
   - Automatic memories created after each synthesis
   - Each memory gets a UUID and timestamp

2. **Retrieval**
   - Semantic search (if embeddings configured)
   - Prefix matching on namespace
   - Exact lookup by memory ID

3. **Updates**
   - Memories can be updated via `update_memory()`
   - Timestamp automatically updated
   - All changes preserved in store

4. **Deletion**
   - Explicit deletion via `delete_memory()`
   - Can be used for cleanup or data management

## Semantic Search

If configured with OpenAI embeddings, agents can perform semantic searches:

```python
memories = await memory_utils.search_memories(
    store,
    user_id,
    query="What are this user's risk preferences?",  # Natural language query
    context="preferences",
    limit=5
)
```

The store will:
1. Embed the query
2. Search stored memories by semantic similarity
3. Return most relevant results ranked by similarity

## Best Practices

### 1. Namespacing
- Use `user_id` consistently for all memory operations
- Use appropriate context types (general, compliance, finance)
- Consider additional namespacing for multi-tenant scenarios

### 2. Memory Content
- Keep memory content focused and concise
- Use structured data (dictionaries/JSON)
- Include timestamps and source information
- Avoid storing duplicate or redundant information

### 3. Privacy & Security
- Memories are scoped to user_id
- Consider what sensitive data to store
- Implement access controls at application level
- Regular cleanup of old/stale memories

### 4. Performance
- Use semantic search when available (more powerful but slower)
- Limit search results with `limit` parameter
- Use context types to silo related memories
- Consider indexing important fields

## Troubleshooting

### Memory Not Found
- Check that `user_id` matches across sessions
- Verify the correct context type is used
- Ensure store is initialized and accessible

### Semantic Search Not Working
- Verify `OPENAI_API_KEY` is set
- Check that embeddings are initialized
- Fall back to exact match if embeddings fail

### Performance Issues
- Reduce `limit` parameter in searches
- Use more specific queries for semantic search
- Consider cleaning up old interactions
- Profile with PostgreSQL EXPLAIN plans

## Migration Guide

To enable memory for existing agents:

1. **Update SessionContext usage**
   ```python
   context = SessionContext(
       thread_id=...,
       user_id=user_id,  # ADD THIS
       model=...,
   )
   ```

2. **Update graph compilation**
   ```python
   agent = await get_compiled_agent("psx_agent", use_postgres=True)
   # Store is now automatically included
   ```

3. **Optional: Add memory tools to agents**
   Already done in compliance_agent.py and finance_agent.py

4. **Optional: Implement custom memory logic**
   - Extend synthesize_node for domain-specific memory handling
   - Add tools to other agents as needed

## API Reference

### Store Functions

- `get_postgres_store()` - Get PostgreSQL store instance
- `get_memory_store()` - Get in-memory store instance
- `get_store(use_postgres: bool)` - Get appropriate store

### Memory Utilities

- `save_memory()` - Save a memory
- `get_memory_by_id()` - Retrieve specific memory
- `search_memories()` - Search with optional semantic query
- `delete_memory()` - Delete a memory
- `update_memory()` - Update existing memory
- `save_preference()` - Save user preference
- `get_preference()` - Retrieve user preference
- `log_interaction()` - Log interaction event
- `get_recent_interactions()` - Get interaction history

### Memory Tools (for agents)

- `save_interaction_memory` - Save memory from agent
- `search_interaction_memories` - Search memories from agent
- `save_user_preference` - Save preference from agent
- `get_user_preference` - Get preference from agent
- `log_user_interaction` - Log interaction from agent
- `get_recent_interaction_history` - Get history from agent

## Examples

See `run_compliance.ipynb` for practical examples of using the memory system.

## References

- [LangGraph Stores Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Long-term Memory](https://docs.langchain.com/llms.txt)
