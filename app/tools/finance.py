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
import re
import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from app.common.utils import  _fetch , _build_kv , perf , _inline_kv , _52w , _company_name , _price , _range_row , _find , _announcements

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

"""
PSX Stock Snapshot — LangChain Tool
Scrapes key investment metrics from scstrade.com for any PSX listed stock.

Usage (LangChain agent):
    from psx_tool import get_stock_snapshot
    tools = [get_stock_snapshot]

Usage (Jupyter / standalone):
    from psx_tool import get_stock_snapshot
    print(get_stock_snapshot.invoke("OGDC"))
"""










# ── LangChain Tool ───────────────────────────────────────────────────────────
@tool
def get_stock_snapshot(symbol: str) -> str:
    """Get key financial metrics for a PSX-listed stock to help decide whether to invest.

    Pass the PSX ticker symbol (e.g. 'EFERT', 'OGDC', 'HBL', 'LUCK').
    Returns current price, EPS, P/E, ROE, dividends, margins, debt ratios,
    52-week range, performance and recent announcements as a readable summary string.
    """
    sym = symbol.strip().upper()

    try:
        soup = _fetch(sym)
    except requests.HTTPError as e:
        return f"Could not fetch data for '{sym}': HTTP {e.response.status_code}. Verify the symbol is correct."
    except Exception as e:
        return f"Error fetching '{sym}': {e}"

    kv      = _build_kv(soup)
    inline  = _inline_kv(soup)
    perf    = _perf(soup)
    low52, high52 = _52w(soup)
    name    = _company_name(soup, sym)

    # ── Price block ───────────────────────────────────────────────
    price   = _price(soup)
    change  = kv.get("__change__", "N/A")
    mktcap  = inline.get("market_cap") or _find(kv, "Market Cap")
    volume  = inline.get("volume",  "N/A")
    beta    = inline.get("beta",    "N/A")
    ff_pct  = inline.get("free_float_pct", "N/A")
    fv      = inline.get("facevalue", "N/A")

    # ── Ranges ────────────────────────────────────────────────────
    day_range = _range_row(soup, "Day`s Range")
    w52_range = f"{low52} – {high52}"
    perf_str  = "  |  ".join(f"{k}: {v}" for k, v in perf.items()) or "N/A"

    # ── Earnings ──────────────────────────────────────────────────
    eps_qtr    = _find(kv, ["Latest EPS"])
    eps_annual = _find(kv, ["Last Annual EPS"])
    pe         = _find(kv, ["Price To Earning P/E"])
    pe_exp     = _find(kv, ["Exp Price To Earning"])
    eps_growth = _find(kv, ["Exp Earning"])

    # ── Dividends ─────────────────────────────────────────────────
    div_annual = _find(kv, ["Last Annual Dividend"])
    div_yield  = _find(kv, ["Dividend Yield"])
    div_exp    = _find(kv, ["Expected Dividend Upto"], ["Expected Dividend"])
    div_cover  = _find(kv, ["Dividend Cover"])
    payout     = _find(kv, ["Payout Ratio"])

    # ── Returns / valuation ───────────────────────────────────────
    roe  = _find(kv, ["Return On Equity"])
    roa  = _find(kv, ["Return On Assets"])
    bvps = _find(kv, ["Book Value Per Share"])
    pb   = _find(kv, ["Price To Book Value"])

    # ── Margins ───────────────────────────────────────────────────
    net_margin   = _find(kv, ["Net Profit Margin"])
    gross_margin = _find(kv, ["Gross Margin"])
    ebitda_m     = _find(kv, ["EBITDA Margin"])

    # ── Health ────────────────────────────────────────────────────
    de_ratio     = _find(kv, ["Debt to Equity Ratio"])
    curr_ratio   = _find(kv, ["Current Ratio"])
    sales_growth = _find(kv, ["Sales Growth (YoY)"])

    # ── Announcements ─────────────────────────────────────────────
    ann_list = _announcements(soup)
    ann_str  = ("\n    • ".join(ann_list)) if ann_list else "None found"

    return f"""
📊 {sym} — {name}
{'='*57}

💰 PRICE
   Current Price    : {price}  ({change})
   Market Cap       : {mktcap}
   Volume (Today)   : {volume}
   Beta             : {beta}  |  Face Value: {fv}
   Free Float       : {ff_pct}

📈 RANGES & PERFORMANCE
   Today's Range    : {day_range}
   52-Week Range    : {w52_range}
   Returns          : {perf_str}

📐 EARNINGS (EPS & P/E)
   EPS (Latest Qtr) : {eps_qtr}
   EPS (Annual)     : {eps_annual}
   P/E Ratio        : {pe}
   Expected P/E     : {pe_exp}
   Expected EPS Δ   : {eps_growth}

💵 DIVIDENDS
   Annual Dividend  : {div_annual}
   Dividend Yield   : {div_yield}
   Expected Div     : {div_exp}
   Dividend Cover   : {div_cover}
   Payout Ratio     : {payout}

📊 RETURNS & VALUATION
   ROE              : {roe}
   ROA              : {roa}
   Book Value/Share : {bvps}
   Price/Book (P/B) : {pb}

💹 MARGINS
   Net Profit Margin  : {net_margin}
   Gross Margin       : {gross_margin}
   EBITDA Margin      : {ebitda_m}

🏦 FINANCIAL HEALTH
   Debt/Equity Ratio  : {de_ratio}
   Current Ratio      : {curr_ratio}
   Sales Growth (YoY) : {sales_growth}

📢 RECENT ANNOUNCEMENTS
    • {ann_str}

{'='*57}
ℹ️  Source: scstrade.com | Symbol: {sym}
""".strip()


# ── Standalone / Jupyter entry ────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 and "ipykernel" not in sys.argv[0] else "EFERT"
    print(get_stock_snapshot.invoke(sym))