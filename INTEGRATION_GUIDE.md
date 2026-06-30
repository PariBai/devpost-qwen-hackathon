# Integration Guide: Enabling Cross-Session Memory

This guide walks you through integrating cross-session memory into your existing LangChain/LangGraph application.

## Changes Overview

The following changes have been made to enable cross-session memory:

### 1. New Modules Created ✓
- **`app/common/store.py`** - Store management (PostgreSQL/in-memory)
- **`app/common/memory.py`** - Memory utilities and core functions
- **`app/tools/memory.py`** - Memory tools for agents
- **`examples/memory_examples.py`** - Usage examples

### 2. Existing Modules Updated ✓
- **`app/common/context.py`** - Added `user_id` field to `SessionContext`
- **`app/graph/compile.py`** - Now passes store to compiled graph
- **`app/agents/compliance_agent.py`** - Added memory tools
- **`app/agents/finance_agent.py`** - Added memory tools
- **`app/graph/nodes.py`** - `synthesize_node` now saves memories

## Step-by-Step Integration

### Step 1: Update Context Creation

**Location:** Wherever you create `SessionContext` instances

**Before:**
```python
context = SessionContext(
    thread_id="thread_123",
    model=your_model,
)
```

**After:**
```python
context = SessionContext(
    thread_id="thread_123",
    user_id="user_456",  # ADD THIS - user identifier for memory namespacing
    model=your_model,
)
```

### Step 2: Update Graph Invocation

**Location:** Wherever you call the compiled agent

**Before:**
```python
agent = await get_compiled_agent("psx_agent")

result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config=config,
    context=context,
)
```

**After:**
```python
# Now includes store automatically
agent = await get_compiled_agent("psx_agent", use_postgres=True)

result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config=config,
    context=context,
)
```

### Step 3: Access Memory in Tools/Nodes

**To access the store in your own tools or nodes:**

```python
from langchain_core.tools import tool
from langchain.tools import ToolRuntime
from app.common.context import SessionContext
from app.common import memory as memory_utils

@tool
async def my_custom_tool(
    param1: str,
    runtime: ToolRuntime[SessionContext],
) -> str:
    """My tool that uses memory."""
    
    # Access store and user context
    if runtime.store is None:
        return "Error: No store available"
    
    user_id = runtime.context.user_id
    
    # Save memory
    memory_id = await memory_utils.save_memory(
        runtime.store,
        user_id,
        {"data": param1},
        context="custom_context",
    )
    
    # Search memories
    memories = await memory_utils.search_memories(
        runtime.store,
        user_id,
        query=param1,
        limit=5,
    )
    
    return f"Saved memory {memory_id} and found {len(memories)} relevant memories"
```

### Step 4: Add Memory Tools to Custom Agents

**If you create custom agents, add memory tools:**

```python
from langchain.agents import create_agent
from app.tools.memory import (
    save_interaction_memory,
    search_interaction_memories,
    get_user_preference,
    save_user_preference,
)

async def get_my_custom_agent():
    return create_agent(
        name="MyAgent",
        model=None,
        system_prompt=YOUR_SYSTEM_PROMPT,
        tools=[
            your_tool_1,
            your_tool_2,
            # Add memory tools
            save_interaction_memory,
            search_interaction_memories,
            get_user_preference,
            save_user_preference,
        ],
        context_schema=SessionContext,
    )
```

### Step 5: Use Memory in Your Nodes

**If you create custom nodes, access memory via Runtime:**

```python
from langgraph.runtime import Runtime
from app.common.context import SessionContext
from app.common import memory as memory_utils

async def my_custom_node(
    state: YourState,
    runtime: Runtime[SessionContext],
):
    # Access memory
    if runtime.store is not None:
        user_id = runtime.context.user_id
        
        # Search for relevant memories
        memories = await memory_utils.search_memories(
            runtime.store,
            user_id,
            query=state["current_query"],
            limit=3,
        )
        
        # Use memories to inform your logic
        memory_context = "\n".join([m.value for m in memories])
        
    # Your logic here...
    return Command(goto="...", update={...})
```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# For PostgreSQL store (production)
DB_URL=postgresql://user:password@localhost:5432/memories
DB_URL_LOCAL=postgresql://user:password@localhost:5432/memories

# Optional: For semantic search (requires OpenAI)
OPENAI_API_KEY=sk-your-key-here
```

### Store Backend Selection

```python
# In-memory store (development/testing)
store = await get_store(use_postgres=False)

# PostgreSQL store (production)
store = await get_store(use_postgres=True)
```

## Usage Examples

### Example 1: Basic Flow

```python
from app.graph.compile import get_compiled_agent
from app.common.context import SessionContext
from app.common.utils import _get_model

async def chat_with_memory():
    # Setup
    agent = await get_compiled_agent("psx_agent", use_postgres=True)
    user_id = "user_123"
    
    context = SessionContext(
        thread_id="thread_001",
        user_id=user_id,
        model=_get_model(),
    )
    
    config = {"configurable": {"thread_id": "thread_001"}}
    
    # First message
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Analyze company ABC"}]},
        config=config,
        context=context,
    )
    # Memory is automatically saved
    
    # Later session, new thread
    new_config = {"configurable": {"thread_id": "thread_002"}}
    context2 = SessionContext(
        thread_id="thread_002",
        user_id=user_id,  # Same user!
        model=_get_model(),
    )
    
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What about company ABC again?"}]},
        config=new_config,
        context=context2,
    )
    # Agent can now search and recall previous findings about ABC
```

### Example 2: Agent Using Memory Tools

```python
# User to agent: "Remember that I like conservative investments"
# Agent uses save_user_preference tool
# saves {"risk_tolerance": "conservative"}

# Later session...
# User to agent: "What's a good investment?"
# Agent uses get_user_preference tool
# retrieves {"risk_tolerance": "conservative"}
# Makes recommendations aligned with user's preference
```

### Example 3: Manual Memory Access

```python
from app.common.store import get_store
from app.common import memory as memory_utils

async def access_user_memories(user_id: str):
    store = await get_store(use_postgres=True)
    
    # Get all memories for a user
    all_memories = await memory_utils.search_memories(
        store,
        user_id,
        limit=100,
    )
    
    # Semantic search
    relevant = await memory_utils.search_memories(
        store,
        user_id,
        query="user's risk preferences",
        limit=5,
    )
    
    # Get interaction history
    history = await memory_utils.get_recent_interactions(
        store,
        user_id,
        limit=20,
    )
```

## Verification

To verify the implementation is working:

1. **Check modules exist:**
   ```bash
   ls -la app/common/store.py
   ls -la app/common/memory.py
   ls -la app/tools/memory.py
   ```

2. **Test imports:**
   ```python
   from app.common.store import get_store
   from app.common import memory
   from app.tools.memory import save_interaction_memory
   ```

3. **Run examples:**
   ```bash
   python examples/memory_examples.py
   ```

4. **Check database:**
   ```bash
   psql postgresql://user:password@localhost:5432/memories -c "SELECT * FROM store_items LIMIT 5;"
   ```

## Troubleshooting

### Issue: "user_id not provided"
**Solution:** Ensure you're passing `user_id` in SessionContext:
```python
context = SessionContext(
    thread_id="...",
    user_id="required_value",  # Don't forget this!
    model=...,
)
```

### Issue: "Store is None"
**Solution:** The store might not be initialized. Check:
1. Graph was compiled with store: `await get_compiled_agent(...)`
2. You're accessing store within a node/tool (not outside)

### Issue: Semantic search not working
**Solution:** 
1. Set `OPENAI_API_KEY` environment variable
2. Ensure `openai` package is installed
3. Fall back to regular search if embeddings fail

### Issue: PostgreSQL connection error
**Solution:**
1. Check DB_URL is correct
2. Verify PostgreSQL is running
3. Try in-memory store for testing: `use_postgres=False`

## Performance Tips

1. **Use context types** to silo memories:
   - `context="general"` for shared learnings
   - `context="compliance"` for compliance findings
   - `context="finance"` for finance findings

2. **Limit search results:**
   ```python
   memories = await memory_utils.search_memories(
       store, user_id,
       limit=5,  # Don't retrieve too many
   )
   ```

3. **Use semantic search sparingly:**
   - Great for finding relevant info
   - More expensive than exact matching
   - Good for retrieval, bad for listing

4. **Regular cleanup:**
   ```python
   # Remove old interactions
   for interaction in old_interactions:
       await memory_utils.delete_memory(
           store, user_id, interaction.key, "interactions"
       )
   ```

## Migration Path

If you have existing sessions without memory:

1. **Old sessions work as before** - No breaking changes
2. **New sessions can use memory** - Add `user_id` to context
3. **Enable for specific users** - Gradual rollout
4. **Opt-in per agent** - Add memory tools where needed

## Next Steps

1. ✓ Review MEMORY_IMPLEMENTATION.md for full documentation
2. ✓ Run examples/memory_examples.py to see it in action
3. ✓ Update your context creation to include `user_id`
4. ✓ Test with `use_postgres=False` first (in-memory)
5. ✓ Configure PostgreSQL for production
6. ✓ Add semantic search with OpenAI (optional)

## Questions?

Refer to:
- [MEMORY_IMPLEMENTATION.md](MEMORY_IMPLEMENTATION.md) - Full documentation
- [examples/memory_examples.py](examples/memory_examples.py) - Usage examples
- [LangGraph Stores Docs](https://langchain-ai.github.io/langgraph/)
