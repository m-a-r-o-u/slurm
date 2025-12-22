"""Plotting helpers for SLURM analytics."""

from __future__ import annotations

from dataclasses import dataclass
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
    output_path: str,
) -> None:
    rows = list(data)
    if not rows:
        raise ValueError("No data available to plot.")

    labels = [row.label for row in rows]
    values = [row.value for row in rows]

    total = sum(values)
    if normalized:
        if total == 0:
            raise ValueError("Total GPU hours are zero; cannot normalize.")
        values = [(value / total) * 100 for value in values]

    sort_descriptor = ""
    if sort_order:
        sort_descriptor = f" (sorted {sort_order})"

    figure_height = max(6.5, 0.4 * len(labels) + 1.0)
    fig, ax = plt.subplots(figsize=(11.0, figure_height))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    positions = np.arange(len(labels))
    ax.barh(positions, values, color="#1f77b4")
    ax.set_yticks(positions, labels)

    if sort_order == "desc":
        ax.invert_yaxis()

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(-0.5, len(labels) - 0.5)
    ax.xaxis.grid(True, linestyle="--", linewidth=0.6, alpha=0.4, color="#6b7280")
    ax.set_axisbelow(True)

    ax.set_xlabel(
        "GPU hours (%)" if normalized else "GPU hours",
        fontsize=13,
        labelpad=8,
        fontfamily="monospace",
    )
    ax.set_ylabel("Project", fontsize=13, labelpad=10, fontfamily="monospace")
    ax.set_title(
        f"GPU hours per project{sort_descriptor}",
        fontsize=15,
        pad=10,
        fontfamily="monospace",
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
