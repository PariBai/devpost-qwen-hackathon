from langgraph.graph import StateGraph
from app.common.state import SessionState
from app.common.context import SessionContext
from app.graph.nodes import (
    init_node,
    compliance_node,
    finance_node,
    synthesize_node,
)


def _create_psx_workflow():
    """Build the PSX due-diligence graph:

        init_node (router)
          ├─► compliance_node ─┐
          └─► finance_node ─────┤   (one or both, in parallel)
                                ▼
                          synthesize_node ─► END

    Edges are inferred from each node's Command(goto=...) plus its Literal return
    hint, so we only register the nodes and the entry point.
    """
    workflow = StateGraph(state_schema=SessionState, context_schema=SessionContext)
    workflow.add_node("init_node", init_node)
    workflow.add_node("compliance_node", compliance_node)
    workflow.add_node("finance_node", finance_node)
    workflow.add_node("synthesize_node", synthesize_node)
    workflow.set_entry_point("init_node")
    return workflow
