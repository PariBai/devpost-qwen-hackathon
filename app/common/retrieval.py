"""
Relevance-based preference recall (Track-1 "recall within a limited context window").

Instead of dumping EVERY stored preference into every agent's prompt, we select only
the ones relevant to the current turn:

  - "always-on" preferences (hard constraints / global style: language, shariah_only,
    risk_tolerance, detail_level, reporting_currency, investment_horizon) are ALWAYS
    injected — a Shariah-only filter must apply even to a query that isn't about Shariah.
  - Everything else (contextual memories: sectors, tickers, and future episodic notes)
    is ranked by semantic similarity to the query via DashScope embeddings, and only the
    top-K are injected.

This scales to thousands of memories and keeps the prompt small + focused. Everything is
wrapped so that if embeddings are unavailable, we fall back to injecting all preferences —
the app never breaks.
"""

import os
import math
from typing import Any, Dict, List, Tuple

# Preferences that must apply to EVERY turn regardless of query similarity.
ALWAYS_ON = {
    "language",
    "shariah_only",
    "risk_tolerance",
    "detail_level",
    "reporting_currency",
    "investment_horizon",
}

# Short natural-language descriptions so semantic search has meaningful text to match
# (the raw value like {"value": true} carries little meaning on its own).
KEY_DESC = {
    "shariah_only": "Shariah compliant halal Islamic investing only, avoid interest-based or haram stocks",
    "language": "preferred language to respond in",
    "risk_tolerance": "risk tolerance and appetite",
    "investment_horizon": "investment time horizon, short term or long term",
    "preferred_sectors": "preferred market sectors to focus on",
    "focus_tickers": "specific stocks or tickers to track",
    "reporting_currency": "currency to report figures in",
    "detail_level": "level of detail or verbosity in answers",
}

_RECALL_K = int(os.getenv("RECALL_K", "3"))

_embeddings = None
_text_cache: Dict[str, List[float]] = {}  # pref-text -> vector (prefs change rarely)


def _get_embeddings():
    """Lazy DashScope embeddings client (OpenAI-compatible endpoint)."""
    global _embeddings
    if _embeddings is None:
        from langchain_openai import OpenAIEmbeddings

        _embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBED_MODEL", "text-embedding-v3"),
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv(
                "DASHSCOPE_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
        )
    return _embeddings


def _short_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return ", ".join(_short_value(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return ", ".join(_short_value(x) for x in v)
    return str(v)


def pref_to_text(key: str, value: Any) -> str:
    """Build the semantic text for a preference from its key description + value."""
    desc = KEY_DESC.get(key, key.replace("_", " "))
    return f"{desc}: {_short_value(value)}".strip()


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def _embed_prefs(texts: List[str]) -> List[List[float]]:
    """Embed preference texts, using a process cache (prefs repeat across turns)."""
    missing = [t for t in texts if t not in _text_cache]
    if missing:
        # DashScope compatible-mode caps batch size; chunk defensively.
        emb = _get_embeddings()
        for i in range(0, len(missing), 10):
            chunk = missing[i : i + 10]
            vecs = await emb.aembed_documents(chunk)
            for t, v in zip(chunk, vecs):
                _text_cache[t] = v
    return [_text_cache[t] for t in texts]


async def select_relevant(
    query: str,
    prefs: Dict[str, Any],
    k: int = _RECALL_K,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Return (selected_prefs, recall_trace).

    selected_prefs: the subset to inject this turn (always-on + top-K contextual).
    recall_trace:   per-preference {key, score, kept, basis} for observability / the UI.
    """
    if not prefs:
        return {}, []

    always = {k_: v for k_, v in prefs.items() if k_ in ALWAYS_ON}
    contextual = {k_: v for k_, v in prefs.items() if k_ not in ALWAYS_ON}

    trace: List[Dict[str, Any]] = [
        {"key": k_, "score": None, "kept": True, "basis": "always-on"} for k_ in always
    ]

    if not contextual:
        return dict(always), trace

    try:
        emb = _get_embeddings()
        qvec = await emb.aembed_query(query)
        keys = list(contextual)
        vecs = await _embed_prefs([pref_to_text(k_, contextual[k_]) for k_ in keys])
        scored = sorted(
            ((_cosine(qvec, v), k_) for v, k_ in zip(vecs, keys)), reverse=True
        )
    except Exception as e:
        # Embeddings unavailable -> inject everything (current behavior). Never break.
        print(f"[recall] semantic recall unavailable, injecting all prefs: {e}")
        for k_ in contextual:
            trace.append({"key": k_, "score": None, "kept": True, "basis": "fallback-all"})
        return dict(prefs), trace

    keep = {k_ for _, k_ in scored[:k]}
    selected = dict(always)
    for score, k_ in scored:
        kept = k_ in keep
        if kept:
            selected[k_] = contextual[k_]
        trace.append(
            {"key": k_, "score": round(score, 3), "kept": kept, "basis": "semantic"}
        )
    return selected, trace
