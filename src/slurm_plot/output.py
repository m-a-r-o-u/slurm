"""Plotting helpers for SLURM analytics."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
import numpy as np


@dataclass(frozen=True)
class BarChartData:
    label: str
    value: float


@dataclass(frozen=True)
class HeatmapData:
    row_labels: Sequence[str]
    column_labels: Sequence[str]
    values: Sequence[Sequence[float]]
    entity_label: str


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

    labels = [row.label for row in rows]
    values = [row.value for row in rows]
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
        return f"{value:,.0f}"

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
        fontsize=18,
        pad=6,
        fontfamily="monospace",
        fontweight="bold",
    )
    ax.set_aspect("equal")

    fig.tight_layout(pad=0.4)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _format_heatmap_value(value: float) -> str:
    if float(value).is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _build_heatmap_boundaries(max_value: float, bin_size: int) -> list[float]:
    if bin_size <= 0:
        raise ValueError("Heatmap bin size must be positive.")
    highest_bin = max(bin_size, int(np.ceil(max_value / bin_size)) * bin_size)
    return [float(value) for value in range(0, highest_bin + bin_size, bin_size)]


def plot_gpu_hours_heatmap(
    data: HeatmapData,
    *,
    output_path: str,
    bin_size: int = 5000,
) -> None:
    if not data.row_labels:
        raise ValueError("No project or user rows available to plot.")
    if not data.column_labels:
        raise ValueError("No quarter columns available to plot.")

    values = np.asarray(data.values, dtype=float)
    if values.shape != (len(data.row_labels), len(data.column_labels)):
        raise ValueError("Heatmap values do not match row and column labels.")

    boundaries = _build_heatmap_boundaries(float(values.max(initial=0)), bin_size)
    colors = plt.get_cmap("YlOrRd", len(boundaries) - 1)(range(len(boundaries) - 1))
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(boundaries, cmap.N, clip=True)

    row_count = len(data.row_labels)
    column_count = len(data.column_labels)
    figure_height = min(60.0, max(5.5, 0.35 * row_count + 2.0))
    figure_width = min(28.0, max(10.0, 1.25 * column_count + 4.0))

    fig, ax = plt.subplots(figsize=(figure_width, figure_height))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.imshow(values, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(np.arange(column_count), labels=data.column_labels)
    ax.set_yticks(np.arange(row_count), labels=data.row_labels)
    ax.set_xticks(np.arange(-0.5, column_count, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, row_count, 1), minor=True)
    ax.grid(which="minor", color="#f9fafb", linestyle="-", linewidth=0.8)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.tick_params(axis="x", labelrotation=45, labelsize=10)
    ax.tick_params(axis="y", labelsize=9)

    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily("monospace")

    for row_index in range(row_count):
        for column_index in range(column_count):
            value = values[row_index, column_index]
            text_color = "white" if value >= boundaries[-1] * 0.6 else "#111827"
            ax.text(
                column_index,
                row_index,
                _format_heatmap_value(value),
                ha="center",
                va="center",
                color=text_color,
                fontsize=8,
                fontfamily="monospace",
            )

    entity_title = "Project" if data.entity_label == "project" else "User"
    ax.set_title(
        f"GPU Hours Used by {entity_title} per Quarter",
        fontsize=16,
        pad=12,
        fontfamily="monospace",
        fontweight="bold",
    )
    ax.set_xlabel("Quarter", fontsize=12, fontfamily="monospace", fontweight="bold")
    ax.set_ylabel(entity_title, fontsize=12, fontfamily="monospace", fontweight="bold")

    for spine in ax.spines.values():
        spine.set_visible(False)

    legend_handles = []
    for index, (lower, upper) in enumerate(zip(boundaries, boundaries[1:])):
        if index == len(boundaries) - 2:
            label = f"{lower:,.0f}+"
        else:
            label = f"{lower:,.0f}–{upper:,.0f}"
        legend_handles.append(
            Patch(facecolor=cmap(index), edgecolor="#e5e7eb", label=label)
        )
    legend = ax.legend(
        handles=legend_handles,
        title="GPU hour bins",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0,
        frameon=False,
    )
    legend.get_title().set_fontfamily("monospace")
    legend.get_title().set_fontweight("bold")
    for text in legend.get_texts():
        text.set_fontfamily("monospace")

    fig.tight_layout(pad=0.5)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
