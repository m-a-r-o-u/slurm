"""Plotting helpers for SLURM analytics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import matplotlib.pyplot as plt


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

    figure_height = max(6.0, 0.35 * len(labels) + 1.5)
    fig, ax = plt.subplots(figsize=(10.5, figure_height))

    ax.barh(labels, values, color="#1f77b4")

    if sort_order == "desc":
        ax.invert_yaxis()

    ax.set_xlabel("GPU hours (%)" if normalized else "GPU hours")
    ax.set_ylabel("Project")
    ax.set_title(f"GPU hours per project{sort_descriptor}")

    ax.tick_params(axis="y", labelsize=10)
    ax.tick_params(axis="x", labelsize=10)

    fig.tight_layout()
    fig.subplots_adjust(left=0.25, right=0.98, top=0.92, bottom=0.08)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
