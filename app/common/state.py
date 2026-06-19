from langgraph.graph import MessagesState
from typing import Any, Optional

class SessionState(MessagesState):
    thread_id: str
    user_query: str
