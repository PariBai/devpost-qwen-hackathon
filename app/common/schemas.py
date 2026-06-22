# app/common/schemas.py
"""
Pydantic schemas for structured LLM outputs.

These are passed as `schema=` to _llm_call(..., structured_output=True), which
runs llm.with_structured_output(schema) so the model returns a validated object
instead of free text. Keep every structured-output schema here so any node can
import it from one place.
"""

from typing import List, Literal
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """Router node output: which specialist agent(s) should handle the query."""

    # A LIST so we can route to one agent (single-domain query) or several at once
    # (a query that spans both domains). `Literal` restricts the values to known
    # agent keys, so the model cannot invent an agent that has no matching node.
    agents: List[Literal["compliance", "finance"]] = Field(
        description=(
            "Specialist agents to invoke for this query. Return exactly the ones "
            "needed: one for a single-domain question, both when the question needs "
            "compliance (broker enforcement) AND finance (company financials). "
            "Must never be empty."
        )
    )

    # Short rationale - handy for debugging/tracing why a route was chosen.
    reason: str = Field(
        description="One short sentence explaining why these agent(s) were chosen."
    )
