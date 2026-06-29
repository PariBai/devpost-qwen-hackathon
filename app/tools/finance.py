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



_BASE_URL = "https://www.scstrade.com/stockscreening/SS_CompanySnapShot.aspx"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.scstrade.com/",
}

# ── Patterns ──────────────────────────────────────────────────────────────────
# A "value" is a financial figure: Rs. X, X %, X x, X bn, X mn, plain number, date
_VALUE_RE = re.compile(
    r"^("
    r"Rs\.\s*[\d,]+\.?\d*"           # Rs. 197.91
    r"|[+\-]?\d[\d,]*\.?\d*\s*%"     # 35.37 %  or  -3.50%
    r"|[+\-]?\d[\d,]*\.?\d*\s*x"     # 6.22 x
    r"|[+\-]?\d[\d,]*\.?\d*\s*bn"    # 264.27 bn
    r"|[+\-]?\d[\d,]*\.?\d*\s*mn"    # 13,352.99 mn
    r"|[+\-]?\d[\d,]*\.?\d*\s*tn"    # 1.44 tn
    r"|\d{2}-[A-Za-z]{3}-\d{4}"      # 04-May-2026  (date)
    r"|N/A"
    r")$",
    re.IGNORECASE,
)
_CHANGE_RE = re.compile(r"^[+\-]\d+\.?\d*\s*\([+\-]\d+\.?\d*%\)$")

SECTION_HEADERS = {
    "Earnings", "Important Ratios", "Equity Ratios", "Dividends",
    "Sales", "Enterprise Value (EV)", "Cash", "Profitablility",
    "Liquidity", "Solvency", "Performance",
}


def _is_value(t: str) -> bool:
    return bool(_VALUE_RE.match(t.strip()))


def _is_section_header(t: str) -> bool:
    return t.strip() in SECTION_HEADERS


# ── Fetch ─────────────────────────────────────────────────────────────────────
def _fetch(symbol: str) -> BeautifulSoup:
    url = f"{_BASE_URL}?symbol={symbol.upper()}"
    s = requests.Session()
    s.get("https://www.scstrade.com/", headers=_HEADERS, timeout=10)
    r = s.get(url, headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ── Core parser ───────────────────────────────────────────────────────────────
def _build_kv(soup: BeautifulSoup) -> dict[str, str]:
    """
    The page layout per section is:
        [Section Header]
        label1  label2  label3  ...   (all labels first)
        value1  value2  value3  ...   (all values after)

    Strategy:
      1. Split the full text stream into sections at each section header.
      2. Within each section, collect labels until we hit values,
         then pair them positionally (label[0]→value[0], etc.).
    """
    all_texts = [t.strip() for t in soup.stripped_strings if t.strip()]

    kv: dict[str, str] = {}

    # Store price change separately
    for t in all_texts:
        if _CHANGE_RE.match(t):
            kv["__change__"] = t
            break

    # Split into sections
    sections: list[list[str]] = []
    current: list[str] = []
    for t in all_texts:
        if _is_section_header(t):
            if current:
                sections.append(current)
            current = [t]  # start new section with header
        else:
            current.append(t)
    if current:
        sections.append(current)

    for section in sections:
        # Within section, labels come before values
        # Find the split point: first index where _is_value is True
        labels = []
        values = []
        hit_values = False
        for t in section[1:]:  # skip section header
            if not hit_values and not _is_value(t):
                labels.append(t)
            else:
                hit_values = True
                if _is_value(t):
                    values.append(t)
                # non-value after values started = ignore (stray text)

        # Pair up positionally
        for label, value in zip(labels, values):
            kv[label] = value

    return kv


def _find(kv: dict, *keyword_groups) -> str:
    """
    Search kv for a label containing ALL words in any keyword group.
    Try groups in order, return first match.
    """
    for group in keyword_groups:
        if isinstance(group, str):
            group = [group]
        group_lower = [k.lower() for k in group]
        for label, val in kv.items():
            ll = label.lower()
            if all(k in ll for k in group_lower):
                return val
    return "N/A"


# ── Specialised extractors ───────────────────────────────────────────────────
def _price(soup: BeautifulSoup) -> str:
    for t in soup.stripped_strings:
        t = t.strip()
        if re.match(r"^Rs\.\s+[\d,]+\.\d{2}$", t):
            return t
    return "N/A"


def _inline_kv(soup: BeautifulSoup) -> dict[str, str]:
    """
    For the top stats section (Volume, Market Cap, Beta, etc.) where each
    label and value appear as adjacent text nodes in the same container.
    """
    result = {}
    # These are rendered as  "Label:\nValue"  pairs in the static block
    label_map = {
        "volume": "Volume",
        "market_cap": "Market Cap",
        "avg_volume": "Avg Volume",
        "paid_up": "Paid Up Capital",
        "auth_cap": "Authorized Capital",
        "total_shares": "Total No. Shares",
        "free_float": "Free Float",
        "beta": "Beta",
        "facevalue": "Facevalue",
        "free_float_pct": "Free Float %",
        "year_end": "Year End",
    }
    texts = [t.strip() for t in soup.stripped_strings if t.strip()]
    for i, t in enumerate(texts):
        for key, label in label_map.items():
            # Label appears with colon suffix in page e.g. "Volume:"
            if t.rstrip(":").strip().lower() == label.lower() and i + 1 < len(texts):
                result[key] = texts[i + 1]
                break
    return result


def _perf(soup: BeautifulSoup) -> dict[str, str]:
    result = {}
    texts = [t.strip() for t in soup.stripped_strings if t.strip()]
    periods = {"1 Month": "1M", "3 Month": "3M", "6 Month": "6M", "1 Year": "1Y"}
    for i, t in enumerate(texts):
        if t in periods and i + 1 < len(texts):
            nxt = texts[i + 1]
            if "%" in nxt:
                result[periods[t]] = nxt
    return result


def _52w(soup: BeautifulSoup) -> tuple[str, str]:
    tag = soup.find(string=lambda t: t and "52 Week" in t)
    if tag:
        row = tag.find_parent("tr")
        if row:
            prices = [c.get_text(strip=True) for c in row.find_all("td") if "Rs." in c.get_text()]
            if len(prices) >= 2:
                return prices[0], prices[1]
    return "N/A", "N/A"


def _range_row(soup: BeautifulSoup, label: str) -> str:
    tag = soup.find(string=lambda t: t and label.lower() in t.lower())
    if tag:
        row = tag.find_parent("tr")
        if row:
            prices = [c.get_text(strip=True) for c in row.find_all("td") if "Rs." in c.get_text()]
            if len(prices) >= 2:
                return f"{prices[0]} – {prices[1]}"
    return "N/A"


def _announcements(soup: BeautifulSoup, n: int = 3) -> list[str]:
    rows = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Ann Type" in headers or "Description" in headers:
            for tr in table.find_all("tr")[1: n + 1]:
                cols = tr.find_all("td")
                if len(cols) >= 3:
                    rows.append(
                        f"[{cols[1].get_text(strip=True)}] "
                        f"{cols[0].get_text(strip=True)}: "
                        f"{cols[2].get_text(strip=True)[:130]}"
                    )
            break
    return rows


def _company_name(soup: BeautifulSoup, symbol: str) -> str:
    h = soup.find(string=lambda t: t and symbol.upper() in t and " - " in t)
    if h:
        parts = h.strip().split(" - ")
        if len(parts) >= 2:
            return parts[1].strip()
    return symbol.upper()


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