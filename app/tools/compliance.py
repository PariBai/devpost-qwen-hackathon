"""
Compliance Agent - database query tool.

The agent writes a SQL SELECT; this tool runs it against the PSX enforcement
SQLite DB and returns the rows.

Safety model (defense in depth):
  1. PRIMARY  - the DB is opened READ-ONLY (mode=ro + PRAGMA query_only).
                Any write (UPDATE/DELETE/DROP/INSERT/...) fails at the engine
                level, no matter how it is phrased or hidden. This is the real
                boundary, not the keyword check below.
  2. Single statement only (no ';' chaining).
  3. Must start with SELECT or WITH.
  4. Friendly secondary keyword guard (nice message for the agent).
  5. Row cap so a huge result can't blow the context / cost.
  6. SQL errors are returned to the agent so it can fix the query and retry.

DB path is read from the DB_PATH environment variable.
"""

import os
import re
import sqlite3
from langchain_core.tools import tool

MAX_ROWS = 200

# secondary guard only - the read-only connection is the actual security boundary
_FORBIDDEN = re.compile(
    r"\b(update|delete|insert|drop|alter|create|replace|attach|detach|"
    r"pragma|vacuum|reindex|truncate)\b",
    re.I,
)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)            # -- line comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)  # /* block comments */
    return sql.strip()


def _validate(sql: str):
    """Return (ok: bool, cleaned_sql_or_message: str)."""
    cleaned = _strip_comments(sql).strip().rstrip(";").strip()
    if not cleaned:
        return False, "Empty query."
    if ";" in cleaned:
        return False, "Only a single SELECT statement is allowed (no ';')."
    if not re.match(r"^(select|with)\b", cleaned, re.I):
        return False, "Only SELECT queries are allowed (it must start with SELECT or WITH)."
    if _FORBIDDEN.search(cleaned):
        return False, "Write operations are not allowed. Use SELECT only."
    return True, cleaned


@tool
def run_sql(query: str) -> str:
    """Run a read-only SQL SELECT query against the PSX enforcement database and return the rows.

    Only SELECT statements are allowed. Use this for every question about PSX
    enforcement actions, brokers, fines, clauses, appeals, etc. The database is
    SQLite. If the query fails, read the returned error, fix the SQL, and call
    this tool again.

    Args:
        query: a single SQLite SELECT statement.
    """
    ok, result = _validate(query)
    if not ok:
        return f"QUERY REJECTED: {result}"
    sql = result

    db_path = os.getenv("DB_PATH")
    if not db_path:
        return "CONFIG ERROR: DB_PATH environment variable is not set."

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        conn.execute("PRAGMA query_only = ON;")
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_ROWS + 1)
        conn.close()
    except sqlite3.Error as e:
        return f"SQL ERROR: {e}\nFix the query and try again."

    if not rows:
        return "No rows returned."

    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]

    lines = [" | ".join(cols)]
    for r in rows:
        lines.append(" | ".join("NULL" if v is None else str(v) for v in r))
    note = f"\n\n[{len(rows)} row(s)" + (f"; truncated to first {MAX_ROWS}" if truncated else "") + "]"
    return "\n".join(lines) + note
