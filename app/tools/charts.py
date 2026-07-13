"""
make_graph — a visualization tool any specialist agent (finance / compliance) can call
to turn the numbers it just pulled into an appealing PNG chart.

Design (see SessionContext.images):
  - The AGENT decides IF a chart helps and, if so, WHICH type, then passes the data it
    already computed. It never touches the filesystem or figures out file names.
  - The tool renders with matplotlib (headless "Agg" backend, thread-safe object-oriented
    API — never pyplot's global state) and saves ONE PNG under:
        charts/<user_id>/<chat_id>/<qid>_chart<N>.png
    so every chart is namespaced per user/chat/turn and a whole chat's charts can be
    removed with one rmtree when the chat is deleted.
  - It appends the public URL ("/charts/...") to runtime.context.images. The API reads
    that list after the answer streams: it persists the names on the chat_history row
    (so reloading a past chat re-shows the charts) and streams an "images" SSE event so
    the current turn renders the chart right after the text.

One schema fits every chart type:
  categories -> x-axis labels (line/bar) · slice labels (pie) · column labels (heatmap)
  series[i]  -> one line / one bar group (line/bar) · the single slice list (pie) ·
                one heatmap row, series[i].name being the row label (heatmap)
"""

import os
import threading
from typing import List, Literal

import matplotlib

matplotlib.use("Agg")  # headless: no GUI, safe on a server. MUST precede pyplot import.

from matplotlib.figure import Figure
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain.tools import ToolRuntime

from app.common.context import SessionContext

CHARTS_DIR = os.getenv("CHARTS_DIR", "charts")

# Brand-aligned, colorful-but-tasteful palette (app accent green + gold + supporting hues).
_PALETTE = ["#0B6E4F", "#C99A2E", "#2F6FEB", "#DC2626", "#7C3AED", "#0891B2", "#EA580C", "#15803D"]
_HEATMAP_CMAP = "YlGnBu"

# matplotlib's font cache / figure teardown isn't guaranteed re-entrant; sync tools run in
# a threadpool, so serialize renders. Cheap insurance — a chart takes a few ms.
_render_lock = threading.Lock()


class Series(BaseModel):
    """One data series: a named list of numbers aligned to `categories`."""
    name: str = Field(description="Legend label for this series (e.g. 'HBL', 'Revenue', '2024').")
    values: List[float] = Field(description="Numbers, one per entry in `categories` (same order/length).")


def _style_axes(ax, title: str, x_label: str, y_label: str) -> None:
    ax.set_title(title, fontsize=13, fontweight="bold", color="#132018", pad=12)
    if x_label:
        ax.set_xlabel(x_label, fontsize=10, color="#5B6B62")
    if y_label:
        ax.set_ylabel(y_label, fontsize=10, color="#5B6B62")
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.4)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(colors="#5B6B62", labelsize=9)


def _render(chart_type, title, categories, series, x_label, y_label, out_path) -> None:
    fig = Figure(figsize=(7, 4.2), dpi=160)
    fig.patch.set_facecolor("white")
    ax = fig.subplots()

    if chart_type == "line":
        for i, s in enumerate(series):
            ax.plot(categories, s.values, marker="o", linewidth=2.2,
                    color=_PALETTE[i % len(_PALETTE)], label=s.name)
        _style_axes(ax, title, x_label, y_label)
        if len(series) > 1:
            ax.legend(frameon=False, fontsize=9)

    elif chart_type in ("bar", "grouped_bar"):
        n = len(series)
        idx = range(len(categories))
        width = 0.8 / max(n, 1)
        for i, s in enumerate(series):
            offsets = [x + (i - (n - 1) / 2) * width for x in idx]
            ax.bar(offsets, s.values, width=width,
                   color=_PALETTE[i % len(_PALETTE)], label=s.name)
        ax.set_xticks(list(idx))
        ax.set_xticklabels(categories, rotation=0)
        _style_axes(ax, title, x_label, y_label)
        if n > 1:
            ax.legend(frameon=False, fontsize=9)

    elif chart_type == "pie":
        values = series[0].values if series else []
        ax.pie(values, labels=categories, autopct="%1.1f%%", startangle=90,
               colors=[_PALETTE[i % len(_PALETTE)] for i in range(len(categories))],
               wedgeprops={"edgecolor": "white", "linewidth": 1.5},
               textprops={"fontsize": 9, "color": "#132018"})
        ax.set_title(title, fontsize=13, fontweight="bold", color="#132018", pad=12)
        ax.axis("equal")

    elif chart_type == "heatmap":
        import numpy as np

        matrix = np.array([s.values for s in series], dtype=float)
        im = ax.imshow(matrix, cmap=_HEATMAP_CMAP, aspect="auto")
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories, rotation=45, ha="right")
        ax.set_yticks(range(len(series)))
        ax.set_yticklabels([s.name for s in series])
        # Annotate each cell so the figures stay readable.
        vmax = matrix.max() if matrix.size else 0
        for r in range(matrix.shape[0]):
            for c in range(matrix.shape[1]):
                val = matrix[r, c]
                ax.text(c, r, f"{val:g}", ha="center", va="center", fontsize=8,
                        color="white" if val > vmax * 0.6 else "#132018")
        ax.set_title(title, fontsize=13, fontweight="bold", color="#132018", pad=12)
        fig.colorbar(im, ax=ax, shrink=0.8)

    fig.tight_layout()
    fig.savefig(out_path, facecolor="white", bbox_inches="tight")


@tool
def make_graph(
    chart_type: Literal["line", "bar", "grouped_bar", "pie", "heatmap"],
    title: str,
    categories: List[str],
    series: List[Series],
    runtime: ToolRuntime[SessionContext],
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Render a chart (PNG) to visualize data you have ALREADY gathered, and attach it to the answer.

    Call this only AFTER you have the real numbers from your other tools, when a visual
    reads better than a table — e.g. a trend over years, comparing companies/metrics, a
    breakdown/share, or a matrix. Do NOT invent numbers to plot; only chart figures you fetched.

    Choose chart_type:
      - "line": trends over an ordered x-axis (e.g. revenue 2021->2025). One line per series.
      - "bar" / "grouped_bar": compare categories; multiple series -> grouped bars.
      - "pie": parts of a whole (one series; categories are the slice labels).
      - "heatmap": a matrix (each series is a row, series.name is the row label, categories
        are the columns).

    Args:
        chart_type: one of line | bar | grouped_bar | pie | heatmap.
        title: a short, descriptive chart title.
        categories: x-axis labels (line/bar) · slice labels (pie) · column labels (heatmap).
        series: the data. Each series has a `name` (legend/row label) and `values` aligned
            to `categories`. Pie uses exactly one series.
        x_label, y_label: optional axis labels (ignored for pie).
        runtime: auto-injected; keep it a BARE ToolRuntime annotation (no Optional/default).

    Returns:
        A short confirmation. The chart is shown to the user automatically — do NOT paste a
        link or markdown image in your text answer; just describe what it shows.
    """
    ctx = runtime.context
    if not categories or not series:
        return "make_graph error: need non-empty `categories` and at least one `series`."

    user_id = str(getattr(ctx, "user_id", "anon"))
    chat_id = str(getattr(ctx, "thread_id", "nochat"))
    qid = getattr(ctx, "qid", None) or 0

    if ctx.images is None:
        ctx.images = []
    n = len(ctx.images) + 1

    rel_dir = os.path.join(CHARTS_DIR, user_id, chat_id)
    os.makedirs(rel_dir, exist_ok=True)
    filename = f"{qid}_chart{n}.png"
    out_path = os.path.join(rel_dir, filename)

    try:
        with _render_lock:
            _render(chart_type, title, categories, series, x_label, y_label, out_path)
    except Exception as e:  # never let a chart failure break the answer
        return f"make_graph could not render the chart ({e}). Answer in text instead."

    # Public URL the frontend loads (StaticFiles mounts CHARTS_DIR at /charts).
    url = f"/charts/{user_id}/{chat_id}/{filename}"
    ctx.images.append(url)
    return f"Chart '{title}' created and attached to the answer ({chart_type})."
