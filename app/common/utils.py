import os
import re
import uuid
import requests  # used by _fetch() to scrape PSX stock pages
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from functools import lru_cache
from langchain.messages import RemoveMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.prompts import PromptTemplate
from typing import List, Set
load_dotenv()


# TODO(qwen): add a 'qwen' branch here (DashScope OpenAI-compatible endpoint)
# and switch the default provider. Keeping the Gemini branch for now so the
# existing pipeline keeps working until we wire Qwen credentials.
@lru_cache(maxsize = 1)
def _get_model(
    name: str,
    temp: Optional[float] = None,
    max_tokens: Optional[int] = None
):
    if name == 'google':
        kwargs = {
            "api_key": os.getenv("GEMINI_API_KEY"),
            "model": "gemini-3-flash-preview",
            "max_retries": 2,
            "temperature": 1.0,
            "max_tokens": None,
            "timeout": None,
            "thinking_level": "low",
            "include_thoughts": False
        }
        if temp is not None:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        model = ChatGoogleGenerativeAI(**kwargs)

    elif name == 'qwen':
        # Qwen via Alibaba Cloud DashScope (OpenAI-compatible endpoint).
        # Lazy import so the module doesn't hard-require langchain-openai
        # unless the Qwen provider is actually used.
        from langchain_openai import ChatOpenAI

        kwargs = {
            "api_key": os.getenv("DASHSCOPE_API_KEY"),
            "base_url": os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
            "model": os.getenv("QWEN_MODEL", "qwen-plus"),
            "temperature": 0,
            "max_retries": 2,
            "timeout": None,
        }
        if temp is not None:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        model = ChatOpenAI(**kwargs)

    else:
        raise ValueError(f"Unsupported Model Name: {name}")

    return model


def _coerce_to_schema(raw, schema):
    """Best-effort recovery when a model emits valid JSON in the WRONG SHAPE for
    `schema`.

    Small / non-frontier models (qwen-flash, qwen2.5-omni-7b, ...) frequently
    "see through" a single-field wrapper and return the inner value directly —
    e.g. `[]` or `[{...}]` instead of `{"ops": [...]}` for PreferenceUpdate, or a
    bare list instead of `{"agents": [...]}` for RouteDecision. Others wrap the
    JSON in prose / ```code fences``` or an extra `{"result": ...}` envelope.

    This takes the raw model message (from with_structured_output(include_raw=True))
    and tries to bend whatever JSON it produced back into `schema`. Model-agnostic,
    so it keeps working as you swap QWEN_MODEL. Returns a schema instance or None.
    """
    import json, re

    # 1) Collect candidate JSON payloads from the raw message.
    candidates = []
    if raw is not None:
        # function-calling mode: the (mis-shaped) data is in the tool-call args.
        for tc in (getattr(raw, "tool_calls", None) or []):
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", None)
            if args is not None:
                candidates.append(args)
        # json / text mode: parse the message content, stripping code fences.
        content = getattr(raw, "content", None)
        if isinstance(content, str) and content.strip():
            text = content.strip()
            m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
            if m:
                text = m.group(1).strip()
            try:
                candidates.append(json.loads(text))
            except Exception:
                pass

    # 2) Try to coerce each candidate into the schema.
    fields = getattr(schema, "model_fields", {}) or {}
    for data in candidates:
        try:
            if isinstance(data, dict):
                try:
                    return schema(**data)
                except Exception:
                    # Unwrap a single-key envelope: {"result": [...]} / {"Schema": {...}}
                    if len(data) == 1:
                        inner = next(iter(data.values()))
                        if isinstance(inner, dict):
                            return schema(**inner)
                        if isinstance(inner, list) and len(fields) == 1:
                            return schema(**{next(iter(fields)): inner})
                    raise
            if isinstance(data, list) and len(fields) == 1:
                # Bare list for a single-field wrapper -> wrap it under that field.
                return schema(**{next(iter(fields)): data})
        except Exception:
            continue
    return None


def _llm_call(
    system_prompt: str,
    user_prompt_template: str,
    user_prompt_inputs: dict,
    llm : Any,
    schema : Any,
    structured_output: bool = False
):

    user_prompt = PromptTemplate(
        input_variables = user_prompt_inputs.keys(),
        template = user_prompt_template
    )

    formatted_user_prompt = user_prompt.format(**user_prompt_inputs)
    messages = [SystemMessage(content = system_prompt), HumanMessage(content = formatted_user_prompt)]

    try:
        if not structured_output:
            response = llm.invoke(messages)
        else:
            # include_raw=True: a schema-validation failure no longer RAISES; instead we
            # get {"raw", "parsed", "parsing_error"} and can recover a mis-shaped reply
            # (e.g. a weak model returning [] instead of {"ops": []}) instead of losing
            # the whole call. Keeps memory writes / routing working across any model.
            structured_llm = llm.with_structured_output(schema, include_raw=True)
            result = structured_llm.invoke(messages)
            response = result.get("parsed") if isinstance(result, dict) else result
            if response is None:
                response = _coerce_to_schema(
                    result.get("raw") if isinstance(result, dict) else None, schema
                )
                if response is not None:
                    print(f"[_llm_call] recovered mis-shaped structured output for "
                          f"{getattr(schema, '__name__', schema)}")
                else:
                    err = result.get("parsing_error") if isinstance(result, dict) else None
                    print(f"[_llm_call] structured output unrecoverable for "
                          f"{getattr(schema, '__name__', schema)}: {err}")

    except Exception as e:
        print(f'Error during LLM call: {e}')
        response = None

    return response


def trim_messages(state):
    """
    Trim messages in the state if there are 8 or more human messages.
    - Remove all messages from the first human up to before the 4th human.
    - Return the updated state dict.
    """
    messages = state["messages"]

    human_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]

    if len(human_indices) < 8:
        return state["messages"]

    fourth_human_idx = human_indices[3]

    messages_to_remove = messages[:fourth_human_idx]

    remove_objects = [RemoveMessage(id = m.id) for m in messages_to_remove]

    return {"messages": remove_objects}


def filter_agent_messages(messages: List, blocked_tools: Set[str]) -> List:
    output_messages = []
    blocked_call_ids = set()

    for m in messages:
        if isinstance(m, AIMessage):
            tool_calls = m.tool_calls or []
            blocked_here = [tc for tc in tool_calls if tc.get("name") in blocked_tools]

            if blocked_here:
                blocked_call_ids.update(tc.get("id") for tc in blocked_here)

            # If every tool call on this AIMessage is blocked, drop the whole message
            # (it's just a request to call a tool the other agent shouldn't see).
            if tool_calls and len(blocked_here) == len(tool_calls):
                continue

            output_messages.append(m)

        elif isinstance(m, ToolMessage):
            if m.name in blocked_tools or m.tool_call_id in blocked_call_ids:
                continue
            output_messages.append(m)

        elif isinstance(m, HumanMessage):
            output_messages.append(m)

    return output_messages

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
