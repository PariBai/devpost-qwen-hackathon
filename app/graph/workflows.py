from langgraph.graph import StateGraph
from app.common.state import SessionState
from app.common.context import SessionContext
from app.graph.nodes import (
    init_node,
    compliance_node,
    finance_node,
    synthesize_node,
    memory_writer_node,
)


def _create_psx_workflow():
    """Build the PSX due-diligence graph:

        init_node (router; also preloads user preferences)
          ├─► compliance_node ─┐
          └─► finance_node ─────┤   (one or both, in parallel)
                                │
                 (2 agents) ────┼──► synthesize_node ─┐
                 (1 agent)  ─────────────────────────┴─► memory_writer_node ─► END

    memory_writer_node is the single exit point: it reflects on the finished turn and
    updates the user's long-term preferences (the WRITE path), whether one agent
    answered directly or synthesize merged two.

    Edges are inferred from each node's Command(goto=...) plus its Literal return
    hint, so we only register the nodes and the entry point.
    """
    workflow = StateGraph(state_schema=SessionState, context_schema=SessionContext)
    workflow.add_node("init_node", init_node)
    workflow.add_node("compliance_node", compliance_node)
    workflow.add_node("finance_node", finance_node)
    workflow.add_node("synthesize_node", synthesize_node)
    workflow.add_node("memory_writer_node", memory_writer_node)
    workflow.set_entry_point("init_node")
    return workflow
