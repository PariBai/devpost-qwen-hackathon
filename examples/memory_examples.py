"""
Example: Using Cross-Session Interaction Memory

This example demonstrates how to use the long-term memory system to store and 
retrieve information across multiple sessions for the same user.
"""

import asyncio
from app.common.context import SessionContext
from app.graph.compile import get_compiled_agent
from app.common.store import get_store
from app.common import memory as memory_utils


async def example_single_session():
    """Example: Single session with automatic memory saving."""
    print("=" * 70)
    print("Example 1: Single Session with Automatic Memory")
    print("=" * 70)
    
    # Setup
    agent = await get_compiled_agent("psx_agent", use_postgres=False)  # Use in-memory for demo
    user_id = "demo_user_1"
    thread_id = "thread_001"
    
    # Create context with user_id
    from app.common.utils import _get_model
    model = _get_model()
    
    context = SessionContext(
        thread_id=thread_id,
        user_id=user_id,
        model=model,
    )
    
    # Invoke agent
    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What is PSX?"}]},
        config=config,
        context=context,
    )
    
    print(f"\nAgent response received")
    print(f"User ID: {user_id}")
    print(f"Thread ID: {thread_id}")
    print("Memory was automatically saved during synthesis!")


async def example_cross_session_memory():
    """Example: Access same user's memory across different sessions/threads."""
    print("\n" + "=" * 70)
    print("Example 2: Cross-Session Memory Access")
    print("=" * 70)
    
    # Setup
    store = await get_store(use_postgres=False)
    user_id = "demo_user_2"
    
    # Session 1: Save a preference
    print("\n[Session 1] Saving user preference...")
    await memory_utils.save_preference(
        store,
        user_id,
        "investment_strategy",
        {
            "risk_tolerance": "moderate",
            "preferred_sectors": ["technology", "finance"],
            "min_investment": 10000,
        }
    )
    print("✓ Preference saved")
    
    # Session 2: Retrieve the preference (simulating new thread/conversation)
    print("\n[Session 2] Retrieving same user's preference from new session...")
    preference = await memory_utils.get_preference(
        store,
        user_id,
        "investment_strategy"
    )
    print(f"✓ Retrieved preference: {preference}")
    
    # Session 3: Save a memory
    print("\n[Session 3] Saving a memory from compliance analysis...")
    memory_id = await memory_utils.save_memory(
        store,
        user_id,
        {
            "finding": "Company XYZ has strong governance structure",
            "details": "All board members passed background checks",
            "date": "2024-06-30",
        },
        context="compliance"
    )
    print(f"✓ Memory saved with ID: {memory_id}")
    
    # Session 4: Search for memories from earlier sessions
    print("\n[Session 4] Searching for memories from previous sessions...")
    memories = await memory_utils.search_memories(
        store,
        user_id,
        query="company governance",  # Semantic search
        context="compliance",
        limit=5
    )
    print(f"✓ Found {len(memories)} memory (ies):")
    for mem in memories:
        print(f"  - {mem.value}")


async def example_interaction_logging():
    """Example: Log and retrieve interaction history."""
    print("\n" + "=" * 70)
    print("Example 3: Interaction Logging and History")
    print("=" * 70)
    
    store = await get_store(use_postgres=False)
    user_id = "demo_user_3"
    
    # Log several interactions
    print("\n[Logging interactions...]")
    for i in range(3):
        interaction_id = await memory_utils.log_interaction(
            store,
            user_id,
            "query_response",
            {
                "query": f"Query {i+1}: Tell me about company {i}",
                "response_summary": f"Company {i} analysis provided",
                "agents_used": ["compliance_node", "finance_node"],
            }
        )
        print(f"✓ Interaction {i+1} logged: {interaction_id}")
    
    # Retrieve interaction history
    print("\n[Retrieving interaction history...]")
    interactions = await memory_utils.get_recent_interactions(
        store,
        user_id,
        limit=10
    )
    print(f"✓ Retrieved {len(interactions)} recent interaction(s):")
    for inter in interactions:
        print(f"  - {inter.value}")


async def example_manual_memory_workflow():
    """Example: Manual memory management workflow."""
    print("\n" + "=" * 70)
    print("Example 4: Manual Memory Management")
    print("=" * 70)
    
    store = await get_store(use_postgres=False)
    user_id = "demo_user_4"
    
    print("\n[Step 1] Saving initial memory...")
    memory_id = await memory_utils.save_memory(
        store,
        user_id,
        {
            "company": "ABC Corp",
            "status": "initial_analysis",
            "score": 75,
        },
        context="finance"
    )
    print(f"✓ Memory created: {memory_id}")
    
    print("\n[Step 2] Retrieving memory...")
    memory = await memory_utils.get_memory_by_id(
        store,
        user_id,
        memory_id,
        context="finance"
    )
    print(f"✓ Retrieved: {memory}")
    
    print("\n[Step 3] Updating memory...")
    await memory_utils.update_memory(
        store,
        user_id,
        memory_id,
        {
            "company": "ABC Corp",
            "status": "updated_analysis",
            "score": 82,
            "last_updated": "2024-06-30",
        },
        context="finance"
    )
    print("✓ Memory updated")
    
    print("\n[Step 4] Retrieving updated memory...")
    updated_memory = await memory_utils.get_memory_by_id(
        store,
        user_id,
        memory_id,
        context="finance"
    )
    print(f"✓ Updated memory: {updated_memory}")
    
    print("\n[Step 5] Deleting memory...")
    await memory_utils.delete_memory(
        store,
        user_id,
        memory_id,
        context="finance"
    )
    print("✓ Memory deleted")
    
    print("\n[Step 6] Verifying deletion...")
    deleted_memory = await memory_utils.get_memory_by_id(
        store,
        user_id,
        memory_id,
        context="finance"
    )
    print(f"✓ Memory is now: {deleted_memory}")


async def main():
    """Run all examples."""
    print("\n" + "🚀 " * 20)
    print("CROSS-SESSION INTERACTION MEMORY EXAMPLES")
    print("🚀 " * 20)
    
    try:
        # Note: These examples may fail if models/utils aren't properly configured
        # They demonstrate the API usage
        
        await example_single_session()
        await example_cross_session_memory()
        await example_interaction_logging()
        await example_manual_memory_workflow()
        
        print("\n" + "✅ " * 20)
        print("All examples completed!")
        print("✅ " * 20 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("\nNote: Some examples require proper model/environment setup.")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
