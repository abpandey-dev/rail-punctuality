"""Charts for the README and notebook. Single-series charts use one hue; labels carry identity, not colour."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
})


def _grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def hbars(labels, values, title, xlabel, fmt="{:.0f}", highlight=None, subtitle=None):
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(labels) + 1.4))
    colors = [BLUE if highlight is None or highlight(l, v) else "#a9c8ee" for l, v in zip(labels, values)]
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=colors, height=0.62)
    span = max(abs(v) for v in values) or 1
    for yi, v in zip(y, values):
        ax.text(v + span * 0.01 if v >= 0 else v - span * 0.01, yi, fmt.format(v), va="center",
                ha="left" if v >= 0 else "right", fontsize=9, color=INK2)
    ax.set_yticks(list(y), labels)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=MUTED, va="bottom")
        ax.title.set_position((0, 1.08))
    ax.axvline(0, color=INK2, linewidth=0.8)
    _grid(ax, "x")
    fig.tight_layout()
    return fig


def by_category(cat: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    y = range(len(cat))[::-1]
    for ax, col, title, fmt in [(axes[0], "on_time_pct", "On time at destination (%)", "{:.0f}%"),
                                (axes[1], "avg_delay_min", "Average delay at destination (min)", "{:.0f}")]:
        vals = cat[col].tolist()
        ax.barh(list(y), vals, color=BLUE, height=0.6)
        for yi, v in zip(y, vals):
            ax.text(v + max(vals) * 0.015, yi, fmt.format(v), va="center", fontsize=9, color=INK2)
        ax.set_yticks(list(y), cat.index.tolist())
        ax.set_title(title)
        _grid(ax, "x")
    axes[1].set_yticklabels([])
    fig.tight_layout()
    return fig


def monthly(month: pd.DataFrame, days: pd.Series):
    """Average delay per month. Months with fewer than 25 days of data are drawn hollow and marked partial."""
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    x = [p.strftime("%b") + ("*" if days[p] < 25 else "") for p in month.index]
    y = month["avg_delay_min"].tolist()
    ax.plot(x, y, color=BLUE, linewidth=2, zorder=2)
    for xi, v, p in zip(x, y, month.index):
        partial = days[p] < 25
        ax.scatter([xi], [v], s=60, color=SURFACE if partial else BLUE, edgecolor=BLUE, linewidth=2, zorder=3)
        ax.annotate(f"{v:.0f}", (xi, v), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=9,
                    color=INK2)
    monsoon = [i for i, p in enumerate(month.index) if p.month in (7, 8, 9)]
    if monsoon:
        ax.axvspan(monsoon[0] - 0.4, monsoon[-1] + 0.4, color="#eef3fb", zorder=0)
    ax.set_ylim(0, max(y) * 1.3)
    if monsoon:
        ax.text(monsoon[0] - 0.3, max(y) * 1.25, "monsoon (Jul-Sep)", color=MUTED, fontsize=9, va="top")
    partial = [f"{p.strftime('%b')} {days[p]} days" for p in month.index if days[p] < 25]
    if partial:
        ax.text(0, -0.2, "* partial month: " + ", ".join(partial), transform=ax.transAxes, fontsize=8.5, color=MUTED)
    ax.set_ylabel("average delay at destination (min)")
    ax.set_title("Delay by month")
    _grid(ax)
    fig.tight_layout()
    return fig


def along_route(stage: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    labels = ["first 20%" if s == "start" else ("last 20%" if s == "end" else s) for s in stage.index.astype(str)]
    ax.bar(labels, stage["mean"], color=BLUE, width=0.6)
    for i, v in enumerate(stage["mean"]):
        ax.text(i, v + stage["mean"].max() * 0.02, f"{v:.0f} min", ha="center", fontsize=9, color=INK2)
    ax.set_ylabel("average delay (min)")
    ax.set_xlabel("position along the route")
    ax.set_title("Delay builds up along the journey")
    _grid(ax)
    fig.tight_layout()
    return fig


def distribution(r: pd.DataFrame, cap: int = 180):
    d = r.loc[r["recorded"], "dest_delay"].clip(-30, cap)
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.hist(d, bins=range(-30, cap + 10, 10), color=BLUE, edgecolor=SURFACE, linewidth=1)
    ax.axvline(15, color=INK2, linestyle="--", linewidth=1)
    ax.text(17, ax.get_ylim()[1] * 0.92, "on-time limit (15 min)", fontsize=9, color=INK2)
    ax.set_xlabel(f"delay at destination (min); the last bar is {cap}+ min")
    ax.set_ylabel("runs")
    ax.set_title("How late do trains arrive?")
    _grid(ax)
    fig.tight_layout()
    return fig


def distance_vs_delay(ranking: pd.DataFrame, highlight: set, title: str, highlight_label: str):
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    hi = ranking.index.isin(list(highlight))
    ax.scatter(ranking.loc[~hi, "distance_km"], ranking.loc[~hi, "avg_delay_min"], s=36, color=BLUE,
               edgecolor=SURFACE, linewidth=1.5, label="other trains")
    ax.scatter(ranking.loc[hi, "distance_km"], ranking.loc[hi, "avg_delay_min"], s=44, color=ORANGE,
               edgecolor=SURFACE, linewidth=1.5, label=highlight_label)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_xlabel("route length (km)")
    ax.set_ylabel("average delay at destination (min)")
    ax.set_title(title)
    _grid(ax, "both")
    fig.tight_layout()
    return fig


def save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
