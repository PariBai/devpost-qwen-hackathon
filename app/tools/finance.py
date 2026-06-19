"""
PSX Finance Agent - financial-summary reader tools.

The financial summaries live as markdown files, one per company and fiscal year:

    <FINANCE_DATA_DIR>/<company>/<year>.md        e.g.  data_md/suzuki/2023.md

Two tools the agent uses:
  - list_financials()                          -> which companies + years exist
  - read_financials(company, year, section)    -> read one file, section-scoped

Design notes:
  * We generate these markdown files, but the exact headers vary per report, so the
    reader is HEADER-driven, not schema-driven:
      - with no `section`, it returns the file's list of section headers (a table of
        contents) so the agent can choose;
      - with a `section`, it returns just that section.
    This keeps the context small and the numbers exact (no whole-file dumps).
  * Output is capped (MAX_CHARS) so a huge section can't blow the context / cost.
  * Company matching is case-insensitive / fuzzy; on a miss the tools return what IS
    available so the agent can self-correct (mirrors the run_sql error-feedback style).

FINANCE_DATA_DIR env var points at the markdown root (default: data_md).
"""

import os
import re
import ast
import operator
from langchain_core.tools import tool
from rapidfuzz import fuzz, process, utils as rf_utils

DATA_DIR = os.getenv("FINANCE_DATA_DIR", "data_md")
MAX_CHARS = 8000
SECTION_MATCH_CUTOFF = 80   # min fuzzy score (0-100) for a header to count as a match
SECTION_MATCH_TOPK = 3      # return at most this many matching sections


def _companies() -> dict:
    """Return {company_folder: [years...]} discovered under DATA_DIR."""
    if not os.path.isdir(DATA_DIR):
        return {}
    out = {}
    for name in sorted(os.listdir(DATA_DIR)):
        d = os.path.join(DATA_DIR, name)
        if not os.path.isdir(d) or name.startswith(("_", ".")):
            continue
        years = sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(d)
            if f.lower().endswith(".md")
        )
        if years:
            out[name] = years
    return out


def _resolve_company(company: str):
    """Match a user-supplied company name to a folder (exact -> case-insensitive -> fuzzy)."""
    comps = _companies()
    if company in comps:
        return company
    low = company.strip().lower()
    for name in comps:
        if name.lower() == low:
            return name
    for name in comps:
        if low and (low in name.lower() or name.lower() in low):
            return name
    return None


def _split_sections(md: str):
    """Split markdown into (level, header, body) tuples by ATX (#..######) headers."""
    sections = []
    cur_head, cur_level, cur_body = None, 0, []
    for ln in md.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", ln.strip())
        if m:
            if cur_head is not None or cur_body:
                sections.append((cur_level, cur_head, "\n".join(cur_body).strip()))
            cur_level = len(m.group(1))
            cur_head = m.group(2).strip()
            cur_body = []
        else:
            cur_body.append(ln)
    if cur_head is not None or cur_body:
        sections.append((cur_level, cur_head, "\n".join(cur_body).strip()))
    return sections


@tool
def list_financials() -> str:
    """List the companies and fiscal years that have financial-summary data available.

    Call this first whenever you are unsure which company or year exists. Returns each
    company id (use it verbatim as the `company` argument) and the years available for it.
    """
    comps = _companies()
    if not comps:
        return f"No financial data found under '{DATA_DIR}'."
    lines = ["Available financial summaries:"]
    for name, years in comps.items():
        lines.append(f"  - {name}: {', '.join(years)}")
    return "\n".join(lines)


@tool
def read_financials(company: str, year: str, section: str = "") -> str:
    """Read a company's financial summary for one fiscal year.

    Recommended workflow:
      1. Call with `section` empty to get the list of section headers in that file.
      2. Call again with one of those headers as `section` to read just that part.

    Args:
        company: company id as shown by list_financials (e.g. 'suzuki').
        year:    fiscal year, e.g. '2023'.
        section: a section header to read; leave empty to list the file's sections.
    """
    comps = _companies()
    resolved = _resolve_company(company)
    if not resolved:
        avail = ", ".join(comps) or "(none)"
        return f"Company '{company}' not found. Available companies: {avail}."

    year = str(year).strip()
    path = os.path.join(DATA_DIR, resolved, f"{year}.md")
    if not os.path.isfile(path):
        return (f"No data for {resolved} {year}. "
                f"Available years for {resolved}: {', '.join(comps[resolved])}.")

    with open(path, encoding="utf-8") as fh:
        md = fh.read()

    sections = _split_sections(md)
    headers = [h for (_lvl, h, _body) in sections if h]

    if not section.strip():
        toc = "\n".join(f"  - {h}" for h in headers) or "  (no headers found)"
        return (f"Sections available in {resolved} {year}:\n{toc}\n\n"
                f"Call read_financials('{resolved}', '{year}', section='<one of the above>') "
                f"to read a section.")

    # The `section` arg is usually an LLM-generated keyword (e.g. "income statement")
    # that won't equal the report's verbose header verbatim. So we fuzzy-score the
    # request against every real header (rapidfuzz WRatio, 0-100) and return the bodies
    # of the top-K headers scoring >= SECTION_MATCH_CUTOFF. This lets a single call land
    # the right section even when the keyword is approximate, instead of a "not found"
    # round-trip. token_set_ratio scores on shared words (ignoring order, length and
    # extra words), so a short keyword like "income statement" matches the verbose
    # "(2) Consolidated Statement of Income ..." header that contains those words.
    want = section.strip()
    header_items = [(h, body) for (_lvl, h, body) in sections if h]

    # process.extract -> list of (matched_header, score, index_into_header_items),
    # already filtered by score_cutoff and sorted by score descending.
    results = process.extract(
        want,
        [h for h, _ in header_items],
        scorer=fuzz.token_set_ratio,
        processor=rf_utils.default_process,   # lowercase + strip punctuation before scoring
        score_cutoff=SECTION_MATCH_CUTOFF,
        limit=SECTION_MATCH_TOPK,
    )
    if not results:
        toc = "\n".join(f"  - {h}" for h in headers)
        return (f"No section in {resolved} {year} matched '{section}' with score "
                f">= {SECTION_MATCH_CUTOFF}. Available sections:\n{toc}")

    parts = []
    for _matched, score, idx in results:
        h, body = header_items[idx]
        parts.append(f"## {h}  (match score: {score:.0f})\n{body}".strip())

    body_text = "\n\n".join(parts)
    text = f"[{resolved} {year}]\n\n{body_text}"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[...truncated...]"
    return text


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------
# LLMs are unreliable at multi-number arithmetic (they predict digits, they do
# not compute), which is the main cause of wrong totals/averages/percentages.
# This tool evaluates the arithmetic exactly so the model never has to. It uses
# a restricted AST walk -- only numbers and + - * / // % ** and parentheses are
# allowed -- so it can NOT run arbitrary Python (no names, calls, attributes).

# allowed binary / unary operators
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node):
    """Recursively evaluate a parsed arithmetic AST node, rejecting anything unsafe."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):                  # a literal number
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("only numeric literals are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


@tool
def calc(expression: str) -> str:
    """Evaluate an arithmetic expression and return the exact result.

    ALWAYS use this for any calculation - sums, differences, averages, percentage
    changes, ratios, margins - instead of computing in your head. Pass the numbers
    you read from read_financials with the operators + - * / ( ) and ** for powers.

    Examples:
        calc("12828592 + 15801848 + 9664429")          -> a total
        calc("(439267 - 416050) / 416050 * 100")        -> a YoY % change
        calc("(160345 + 221107 + 267717) / 3")          -> an average

    Use plain digits only (no commas, currency symbols or units).
    """
    # strip thousands-separators / currency noise so "1,234" or "¥1,234" still works,
    # then strip whitespace again (a leftover leading space breaks ast.parse)
    expr = (expression.replace(",", "").replace("¥", "").replace("Rs", "")
            .replace("$", "").strip())
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree)
    except ZeroDivisionError:
        return f"Cannot evaluate '{expression}': division by zero."
    except Exception:
        return (f"Cannot evaluate '{expression}'. Use only numbers and + - * / ( ) ** , "
                f"e.g. calc(\"(439267 - 416050) / 416050 * 100\").")
    # present ints without a trailing .0; round floats to a sensible precision
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    if isinstance(result, float):
        result = round(result, 6)
    return f"{expression} = {result}"
