# app/prompts/memory_writer.py
"""
Prompts for memory_writer_node - the post-turn reflection step that maintains the
user's LONG-TERM preference memory.

This node runs AFTER the answer has streamed to the user, so it never adds latency
to the visible response. It reads the finished turn (user query + final answer) plus
the user's existing preferences, and decides which preferences to upsert/delete.

Design rules encoded in the prompt:
  - Store ONLY durable, cross-session preferences (not one-off questions or facts).
  - REUSE existing keys when updating (prevents duplicate / contradictory keys).
  - DELETE when the user revokes/contradicts a stored preference (timely forgetting).
  - Return an EMPTY ops list when nothing durable was expressed (the common case).
"""

MEMORY_WRITER_SYSTEM_PROMPT = """You maintain a user's LONG-TERM preference memory for a
Pakistan Stock Exchange (PSX) finance & compliance assistant. Your job is to look at the
latest turn and decide what durable preferences to remember, update, or forget.

STORE ONLY durable, cross-session preferences - things that stay true across many future
conversations. Examples:
- risk tolerance (e.g. conservative / aggressive)
- preferred sectors or specific tickers to focus on
- reporting preferences (currency, language, level of detail)
- compliance constraints (e.g. Shariah-compliant only)

NEVER store:
- one-off questions or their factual answers (e.g. "what is HBL's P/E ratio")
- transient, single-query context
- anything specific to just this one message

RULES:
- REUSE an existing key when the new information updates it. Do NOT create a near-duplicate
  key (e.g. never add 'sector_pref' when 'preferred_sectors' already exists).
- Use action 'delete' when the user contradicts, revokes, or no longer wants a stored
  preference - this is how outdated memory is forgotten in time.
- Use action 'upsert' to add a new preference or replace the value of an existing one.
- Keys are semantic snake_case. Values are small JSON objects.
- If the turn expressed NOTHING durable, return an empty ops list. This is normal and expected.
- Preferences almost always come from what the USER said; the assistant answer is only context.
"""

# Filled by _llm_call / formatted before the model call (single-brace {placeholders}).
# NOTE: these placeholder names MUST match the keys passed in memory_writer_node's
# user_prompt_inputs dict, or PromptTemplate.format() raises KeyError.
MEMORY_WRITER_USER_TEMPLATE = """Current stored preferences (key -> value):
{existing_preferences}

--- Latest turn ---
User said:
{current_user_query}

Assistant answered:
{previous_assistant_answer}

Decide the preference changes for this turn (upsert / delete), reusing existing keys where
they apply. Return an empty ops list if nothing durable was expressed."""
