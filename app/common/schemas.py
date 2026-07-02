# app/common/schemas.py
"""
Pydantic schemas for structured LLM outputs.

These are passed as `schema=` to _llm_call(..., structured_output=True), which
runs llm.with_structured_output(schema) so the model returns a validated object
instead of free text. Keep every structured-output schema here so any node can
import it from one place.
"""

from typing import List, Literal, Dict, Any
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """Router node output: which specialist agent(s) should handle the query."""

    # A LIST so we can route to one agent (single-domain query) or several at once
    # (a query that spans both domains). `Literal` restricts the values to known
    # agent keys, so the model cannot invent an agent that has no matching node.
    agents: List[Literal["compliance_node", "finance_node", "__end__"]] = Field(
        description=(
            "Specialist agents to invoke for this query. Return exactly the ones "
            "needed: one for a single-domain question, both when the question needs "
            "compliance (broker enforcement) AND finance (company financials). "
            "Must never be empty."
        )
    )

    # Short rationale - handy for debugging/tracing why a route was chosen.
    # reason: str = Field(
    #     description="One short sentence explaining why these agent(s) were chosen."
    # )


class PreferenceOp(BaseModel):
    """A single change to the user's long-term preference store.

    Emitted by memory_writer_node's reflection LLM call. This is the unit of the
    WRITE path: the agent never decides to save; the writer reflects on the finished
    turn and produces these ops (often none).
    """

    action: Literal["upsert", "delete"] = Field(
        description=(
            "'upsert' to add a new preference OR replace an existing one; "
            "'delete' to FORGET an outdated preference the user has revoked/contradicted."
        )
    )
    key: str = Field(
        description=(
            "Canonical snake_case preference key, e.g. 'risk_tolerance', "
            "'preferred_sectors', 'reporting_currency', 'compliance_filter'. "
            "REUSE an existing key when this updates a known preference - never invent "
            "a near-duplicate (e.g. do not add 'sector_pref' when 'preferred_sectors' exists)."
        )
    )
    value: Dict[str, Any] = Field(
        default_factory=dict,
        description="Preference payload for 'upsert'. Ignored for 'delete'.",
    )
    reason: str = Field(
        description="One short sentence explaining this change (used for tracing / demo visualization)."
    )


class PreferenceUpdate(BaseModel):
    """memory_writer_node output: the set of preference changes for THIS turn.

    An empty ops list is the common case - it means the turn contained nothing
    durable worth remembering, so the store is left untouched.
    """

    ops: List[PreferenceOp] = Field(
        default_factory=list,
        description="Preference changes to apply. Empty list = remember nothing this turn.",
    )
