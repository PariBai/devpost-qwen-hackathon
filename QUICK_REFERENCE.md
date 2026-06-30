# Quick Reference: Cross-Session Memory

Quick lookup guide for common memory operations.

## Essential Setup

### 1. Creating Context (REQUIRED)
```python
from app.common.context import SessionContext

context = SessionContext(
    thread_id="thread_123",
    user_id="user_456",          # ← IMPORTANT!
    model=your_model,
)
```

### 2. Getting the Agent (REQUIRED)
```python
from app.graph.compile import get_compiled_agent

# Automatically includes store now
agent = await get_compiled_agent("psx_agent", use_postgres=True)
```

### 3. Invoking the Agent
```python
config = {"configurable": {"thread_id": "thread_123"}}

result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config=config,
    context=context,
)
# Memories are automatically saved!
```

---

## Memory Operations (Manual)

### Get the Store
```python
from app.common.store import get_store

# Development (in-memory)
store = await get_store(use_postgres=False)

# Production (PostgreSQL)
store = await get_store(use_postgres=True)
```

### Save a Memory
```python
from app.common import memory as memory_utils

memory_id = await memory_utils.save_memory(
    store, user_id,
    {"finding": "Company XYZ is strong", "rating": 8},
    context="finance"
)
```

### Search Memories
```python
# Semantic search
memories = await memory_utils.search_memories(
    store, user_id,
    query="company performance",
    context="finance",
    limit=5
)

# List all (no query)
all_memories = await memory_utils.search_memories(
    store, user_id,
    limit=100
)
```

### Get Specific Memory
```python
memory = await memory_utils.get_memory_by_id(
    store, user_id, memory_id, context="finance"
)
```

### Update Memory
```python
await memory_utils.update_memory(
    store, user_id, memory_id,
    {"finding": "Updated info", "rating": 9},
    context="finance"
)
```

### Delete Memory
```python
await memory_utils.delete_memory(
    store, user_id, memory_id, context="finance"
)
```

---

## User Preferences

### Save Preference
```python
from app.common import memory as memory_utils

await memory_utils.save_preference(
    store, user_id, "risk_tolerance",
    {"level": "moderate", "max_loss": 0.2}
)
```

### Get Preference
```python
preference = await memory_utils.get_preference(
    store, user_id, "risk_tolerance"
)
```

---

## Interaction Logging

### Log Interaction
```python
from app.common import memory as memory_utils

interaction_id = await memory_utils.log_interaction(
    store, user_id,
    "query_response",
    {"query": "What about ABC?", "result": "Analysis..."}
)
```

### Get Recent Interactions
```python
interactions = await memory_utils.get_recent_interactions(
    store, user_id, limit=10
)
```

---

## Agent Memory Tools

When agents want to use memory, they invoke these tools:

### Agent: Save Memory
> "I should remember this compliance issue for future reference"

```
Tool: save_interaction_memory
Args: memory_content, context_type
Returns: "Memory saved with ID: xxx"
```

### Agent: Search Memory
> "What compliance issues did we find before?"

```
Tool: search_interaction_memories
Args: query, context_type
Returns: List of relevant memories
```

### Agent: Get User Preference
> "What's the user's investment style?"

```
Tool: get_user_preference
Args: preference_key
Returns: Preference dict or "Not found"
```

### Agent: Save Preference
> "The user prefers conservative strategies"

```
Tool: save_user_preference
Args: preference_key, preference_value
Returns: "Saved successfully"
```

---

## Memory Namespaces

```
user_id = "user_123"

General Memories:
  Namespace: (user_id, "memories", "general")
  Use for: Cross-domain learnings, facts

Compliance Memories:
  Namespace: (user_id, "memories", "compliance")
  Use for: Compliance findings, regulatory info

Finance Memories:
  Namespace: (user_id, "memories", "finance")
  Use for: Financial analysis, market data

Preferences:
  Namespace: (user_id, "preferences")
  Keys: "risk_tolerance", "investment_style", etc.

Interactions:
  Namespace: (user_id, "interactions")
  Tracks: queries, responses, patterns
```

---

## Common Patterns

### Pattern 1: Save Finding from Compliance Analysis
```python
# In compliance_node or compliance_agent
if runtime.store is not None:
    await memory_utils.save_memory(
        runtime.store, runtime.context.user_id,
        {
            "type": "compliance_finding",
            "company": "ABC Corp",
            "issue": "Missing audit documentation",
            "severity": "high",
        },
        context="compliance"
    )
```

### Pattern 2: Use Previous Findings in Analysis
```python
if runtime.store is not None:
    memories = await memory_utils.search_memories(
        runtime.store, runtime.context.user_id,
        query=f"company {company_name}",
        context="compliance",
        limit=3
    )
    for mem in memories:
        # Incorporate into analysis
        previous_findings.append(mem.value["issue"])
```

### Pattern 3: Respect User Preferences
```python
if runtime.store is not None:
    pref = await memory_utils.get_preference(
        runtime.store, runtime.context.user_id,
        "risk_tolerance"
    )
    if pref and pref["level"] == "conservative":
        # Adjust recommendations
        pass
```

### Pattern 4: Track Conversation History
```python
# Log at end of interaction
await memory_utils.log_interaction(
    runtime.store, runtime.context.user_id,
    "query_response",
    {
        "query": state["messages"][-1].content,
        "agents": runtime.context.agents,
        "timestamp": datetime.now().isoformat(),
    }
)
```

---

## Environment Variables

```bash
# Minimal (development)
# Nothing required - uses in-memory store

# Production
DB_URL=postgresql://user:password@localhost:5432/memories
DB_URL_LOCAL=postgresql://user:password@localhost:5432/memories

# Optional: Semantic search
OPENAI_API_KEY=sk-...
```

---

## Debugging

### Check if Store is Initialized
```python
if runtime.store is None:
    print("ERROR: Store not initialized")
```

### List All Namespaces for User
```python
from app.common import memory as memory_utils

namespaces = await store.alist_namespaces(
    prefix=(user_id,),
    max_depth=2
)
for ns in namespaces:
    print(f"Namespace: {ns}")
```

### Get All Memories for User
```python
all_memories = await store.asearch(
    (user_id, "memories"),
    limit=1000
)
print(f"Total memories: {len(all_memories)}")
```

### Check Memory Content
```python
item = await store.aget((user_id, "memories", "finance"), memory_id)
if item:
    print(item.dict())  # Pretty print with metadata
else:
    print("Memory not found")
```

---

## Error Handling

### Handle Missing Store
```python
if runtime.store is None:
    # Fallback behavior
    return "Store not available"
```

### Handle Missing Memory
```python
memory = await memory_utils.get_memory_by_id(store, user_id, mem_id)
if memory is None:
    print(f"Memory {mem_id} not found")
```

### Handle Search Empty Results
```python
results = await memory_utils.search_memories(store, user_id, query="...")
if not results:
    print("No relevant memories found")
```

---

## Performance Tips

### 1. Limit Search Results
```python
# Good
memories = await memory_utils.search_memories(
    store, user_id, limit=5  # Keep it reasonable
)

# Bad
memories = await memory_utils.search_memories(
    store, user_id, limit=10000  # Too many!
)
```

### 2. Use Context Types
```python
# Good - semantic search in specific context
memories = await memory_utils.search_memories(
    store, user_id, query="...", context="finance", limit=5
)

# Slower - search all contexts
memories = await memory_utils.search_memories(
    store, user_id, query="...", limit=50
)
```

### 3. Semantic Search Sparingly
```python
# Use for: Finding relevant information
results = await store.asearch(
    namespace, query="user preferences", limit=5
)

# Don't use for: Just listing/browsing
results = await store.asearch(
    namespace, limit=100  # No query
)
```

---

## Checklists

### Enabling Memory for a Session
- [ ] Import `SessionContext` from `app/common/context`
- [ ] Add `user_id` parameter when creating context
- [ ] Call `get_compiled_agent()` with store support
- [ ] Pass context to `agent.ainvoke()`
- [ ] Memory will auto-save (no other changes needed)

### Adding Memory Tools to Agent
- [ ] Import memory tools from `app/tools/memory`
- [ ] Add to agent's tool list in `create_agent()`
- [ ] Agent can now invoke them during reasoning
- [ ] No code changes in agent logic needed

### Accessing Memory in Custom Node
- [ ] Add `runtime: Runtime[SessionContext]` parameter
- [ ] Check `if runtime.store is not None`
- [ ] Import memory utilities
- [ ] Use `runtime.context.user_id` for namespace
- [ ] Await async memory operations

---

## Resources

- **Full Docs**: [MEMORY_IMPLEMENTATION.md](../MEMORY_IMPLEMENTATION.md)
- **Integration**: [INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md)
- **Examples**: [examples/memory_examples.py](../examples/memory_examples.py)
- **Summary**: [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)

---

**Last Updated**: 2024-06-30
**Version**: 1.0
