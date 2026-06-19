from langgraph.graph import StateGraph
from app.common.state import SessionState
from app.common.context import SessionContext
from app.graph.nodes import init_node, compliance_node

def _create_compliance_workflow():
    workflow = StateGraph(state_schema = SessionState, context_schema = SessionContext)
    workflow.add_node("init_node", init_node)
    workflow.add_node("compliance_node", compliance_node)
    workflow.set_entry_point("init_node")
    return workflow
