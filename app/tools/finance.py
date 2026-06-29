"""
PSX Finance Agent - tools for a single-file financial data store.

All company data lives in ONE markdown file:

    <FINANCE_DATA_FILE>   (default: data_md/psx_financials.md)

Structure of that file:
    # Company Name          <- H1  = company block
    ## Section Name         <- H2  = sections within that company block
    | table rows |

Two tools:
  list_financials()          -> which companies exist
  read_financials(company)   -> returns the full data block for that company
  calc(expression)           -> exact arithmetic (never compute in your head)
"""

import os
import re
import ast
import operator
from langchain_core.tools import tool
from rapidfuzz import fuzz, process, utils as rf_utils

DATA_FILE = os.getenv("FINANCE_DATA_FILE", "data_md/psx_financials.md")

MAX_CHARS = 8000


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _load_file() -> str:
    """Read the master markdown file, return its text (or empty string on missing)."""
    if not os.path.isfile(DATA_FILE):
        return ""
    with open(DATA_FILE, encoding="utf-8") as fh:
        return fh.read()


def _split_companies(md: str) -> dict:
    """
    Split the markdown into {company_name: company_block_text} using H1 headers.
    The block text includes all lines up to (but not including) the next H1.
    """
    companies = {}
    cur_name = None
    cur_lines = []

    for line in md.splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            if cur_name is not None:
                companies[cur_name] = "\n".join(cur_lines).strip()
            cur_name = m.group(1).strip()
            cur_lines = []
        else:
            if cur_name is not None:
                cur_lines.append(line)

    if cur_name is not None:
        companies[cur_name] = "\n".join(cur_lines).strip()

    return companies


def _resolve_company(name: str, companies: dict) -> str | None:
    """
    Match a user-supplied name to a company key.
    Priority: exact → case-insensitive → substring → fuzzy.
    """
    if name in companies:
        return name
    low = name.strip().lower()
    for k in companies:
        if k.lower() == low:
            return k
    for k in companies:
        if low in k.lower() or k.lower() in low:
            return k
    results = process.extract(
        name, list(companies.keys()),
        scorer=fuzz.token_set_ratio,
        processor=rf_utils.default_process,
        score_cutoff=60,
        limit=1,
    )
    return results[0][0] if results else None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def list_financials() -> str:
    """List all companies that have financial data available.

    Call this whenever you are unsure which company names exist.
    Returns each company name exactly as it should be passed to read_financials.
    """
    md = _load_file()
    if not md:
        return f"Financial data file not found at '{DATA_FILE}'."
    companies = _split_companies(md)
    if not companies:
        return f"No company sections (H1 headers) found in '{DATA_FILE}'."
    lines = ["Available companies:"]
    for name in companies:
        lines.append(f"  - {name}")
    return "\n".join(lines)


@tool
def read_financials(company: str) -> str:
    """Read all financial data for a company.

    Returns the company's complete data block: metadata (currency, units, source,
    years covered), income statement, and ratios — everything in one call.

    Args:
        company: company name as shown by list_financials (e.g. 'Honda Atlas Cars').
                 Partial or approximate names are resolved automatically.
    """
    md = _load_file()
    if not md:
        return f"Financial data file not found at '{DATA_FILE}'."

    companies = _split_companies(md)
    resolved = _resolve_company(company, companies)
    if not resolved:
        avail = ", ".join(companies) or "(none)"
        return f"Company '{company}' not found. Available companies: {avail}."

    text = f"# {resolved}\n\n{companies[resolved]}"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[...truncated...]"
    return text


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

_BIN_OPS = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:      operator.mod,
    ast.Pow:      operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


@tool
def calc(expression: str) -> str:
    """Evaluate an arithmetic expression and return the exact result.

    ALWAYS use this for any calculation — sums, differences, averages, percentage
    changes, ratios, margins — instead of computing in your head.

    Examples:
        calc("122283 + 78066")                         -> a total
        calc("(3234 - 2709) / 2709 * 100")             -> YoY % change
        calc("(3234 + 2709 + 2334 + 260) / 4")        -> an average

    Use plain digits only (no commas, currency symbols or units).
    """
    expr = (expression
            .replace(",", "")
            .replace("¥", "")
            .replace("Rs", "")
            .replace("$", "")
            .strip())
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree)
    except ZeroDivisionError:
        return f"Cannot evaluate '{expression}': division by zero."
    except Exception:
        return (
            f"Cannot evaluate '{expression}'. "
            f"Use only numbers and + - * / ( ) ** , "
            f'e.g. calc("(3234 - 2709) / 2709 * 100").'
        )

    if isinstance(result, float) and result.is_integer():
        result = int(result)
    if isinstance(result, float):
        result = round(result, 6)
    return f"{expression} = {result}"