"""Plotting helpers for SLURM analytics."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class BarChartData:
    label: str
    value: float


def plot_gpu_hours_horizontal_bar(
    data: Iterable[BarChartData],
    *,
    normalized: bool,
    sort_order: str,
    title: str | None,
    output_path: str,
) -> None:
    rows = list(data)
    if not rows:
        raise ValueError("No data available to plot.")

    total = sum(row.value for row in rows)
    if normalized:
        if total == 0:
            raise ValueError("Total GPU hours are zero; cannot normalize.")
        values = [(value / total) * 100 for value in values]

    title_suffix = f" ({title})" if title else ""

    figure_height = max(6.5, 0.4 * len(labels) + 1.0)
    fig, ax = plt.subplots(figsize=(11.0, figure_height))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    positions = np.arange(len(labels))
    ax.barh(positions, values, color="#1f77b4")
    ax.set_yticks(positions, labels)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if sort_order == "desc":
        ax.set_ylim(len(labels) - 0.5, -0.5)
    else:
        ax.set_ylim(-0.5, len(labels) - 0.5)
    ax.xaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.4, color="#6b7280")
    ax.set_axisbelow(True)

    ax.set_xlabel(
        "GPU hours (%)" if normalized else "GPU hours",
        fontsize=13,
        labelpad=8,
        fontfamily="monospace",
        fontweight="bold",
    )
    ax.set_ylabel(
        "Project",
        fontsize=13,
        labelpad=10,
        fontfamily="monospace",
        fontweight="bold",
    )
    ax.set_title(
        f"GPU hours per project{title_suffix}",
        fontsize=15,
        pad=10,
        fontfamily="monospace",
        fontweight="bold",
    )

    ax.tick_params(axis="y", labelsize=11)
    ax.tick_params(axis="x", labelsize=11)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily("monospace")
    ax.margins(y=0.01)

    fig.tight_layout(pad=0.4)
    fig.subplots_adjust(left=0.27, right=0.98, top=0.96, bottom=0.06)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def plot_gpu_hours_donut_chart(
    data: Iterable[BarChartData],
    *,
    normalized: bool,
    title: str | None,
    output_path: str,
) -> None:
    rows = list(data)
    if not rows:
        raise ValueError("No data available to plot.")

    total = sum(row.value for row in rows)
    if total <= 0:
        raise ValueError("Total GPU hours are zero; cannot plot donut chart.")

    others_threshold = total * 0.02
    major_rows: list[BarChartData] = []
    others_total = 0.0
    for row in rows:
        if row.value < others_threshold:
            others_total += row.value
        else:
            major_rows.append(row)

    major_rows.sort(key=lambda item: item.value)

    chart_rows: list[BarChartData] = []
    if others_total > 0:
        chart_rows.append(BarChartData(label="Others", value=others_total))
    chart_rows.extend(major_rows)

    chart_labels = [row.label for row in chart_rows]
    chart_values = [row.value for row in chart_rows]
    if normalized:
        chart_values = [(value / total) * 100 for value in chart_values]

    title_suffix = f" ({title})" if title else ""

    fig, ax = plt.subplots(figsize=(10.5, 10.5))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    colors = [
        "#d3d3d3" if label == "Others" else None for label in chart_labels
    ]
    palette = plt.get_cmap("tab20")
    color_iter = cycle(palette.colors)
    resolved_colors = []
    for label, color in zip(chart_labels, colors):
        if color is not None:
            resolved_colors.append(color)
        else:
            resolved_colors.append(next(color_iter))

    def _format_label(pct: float) -> str:
        if normalized:
            return f"{pct:.1f}%"
        value = (pct / 100) * total
        return f"{value:,.0f}h"

    wedges, texts, autotexts = ax.pie(
        chart_values,
        labels=chart_labels,
        startangle=90,
        counterclock=False,
        colors=resolved_colors,
        autopct=_format_label,
        pctdistance=0.8,
        labeldistance=1.08,
        wedgeprops={"width": 0.35, "edgecolor": "white"},
    )

    for text in texts + autotexts:
        text.set_fontfamily("monospace")
        text.set_fontsize(12)
        text.set_fontweight("bold")
    ax.set_title(
        f"GPU hours per project{title_suffix}",
        fontsize=16,
        pad=14,
        fontfamily="monospace",
        fontweight="bold",
    )
    ax.set_aspect("equal")

    fig.tight_layout(pad=0.4)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
