"""Command-line interface for SLURM plotting utilities."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from io import StringIO
from typing import Iterable, Sequence

from .plots import BarChartData, plot_gpu_hours_horizontal_bar


@dataclass(frozen=True)
class GpuHoursRecord:
    account: str
    gpu_hours: float


def _parse_bool(value: str) -> bool:
    value_lower = value.strip().lower()
    if value_lower in {"true", "1", "yes", "y"}:
        return True
    if value_lower in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean value (true/false).")


def _read_csv_content(input_path: str | None) -> str:
    if input_path:
        with open(input_path, "r", encoding="utf-8") as handle:
            return handle.read()

    if sys.stdin.isatty():
        raise SystemExit("Provide --input or pipe CSV data via stdin.")

    return sys.stdin.read()


def _load_gpu_hours(csv_content: str) -> list[GpuHoursRecord]:
    reader = csv.DictReader(StringIO(csv_content))
    if reader.fieldnames is None:
        raise SystemExit("CSV data is missing headers.")

    required_fields = {"account", "gpu_hours"}
    if not required_fields.issubset(set(reader.fieldnames)):
        missing = ", ".join(sorted(required_fields.difference(set(reader.fieldnames))))
        raise SystemExit(f"CSV data missing required columns: {missing}")

    records: list[GpuHoursRecord] = []
    for row in reader:
        account = str(row.get("account", "")).strip()
        if not account:
            continue
        try:
            gpu_hours = float(row.get("gpu_hours", 0) or 0)
        except ValueError as exc:
            raise SystemExit(f"Invalid gpu_hours value: {row.get('gpu_hours')}") from exc
        records.append(GpuHoursRecord(account=account, gpu_hours=gpu_hours))

    if not records:
        raise SystemExit("No valid rows found in the CSV data.")

    return records


def _aggregate_gpu_hours(records: Iterable[GpuHoursRecord]) -> list[BarChartData]:
    totals: dict[str, float] = defaultdict(float)
    for record in records:
        totals[record.account] += record.gpu_hours

    return [BarChartData(label=account, value=hours) for account, hours in totals.items()]


def _sort_and_trim(data: list[BarChartData], sort_order: str, n: int | None) -> list[BarChartData]:
    ordered = data
    if sort_order:
        reverse = sort_order == "desc"
        ordered = sorted(data, key=lambda item: item.value, reverse=reverse)

    if n is not None:
        if n <= 0:
            raise SystemExit("--n must be a positive integer.")
        ordered = ordered[:n]

    return ordered


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slurm-plot",
        description=(
            "Plotting utilities for SLURM analytics datasets. Use subcommands to generate charts."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    bar_parser = subparsers.add_parser(
        "horizontal-bar-chart-gpuhours",
        help="Plot a horizontal bar chart of GPU hours per project.",
    )
    bar_parser.add_argument(
        "--input",
        type=str,
        help="Path to a CSV file with year, account, and gpu_hours columns (defaults to stdin).",
    )
    bar_parser.add_argument(
        "--output",
        type=str,
        default="gpu-hours.png",
        help="Output path for the chart image (defaults to gpu-hours.png).",
    )
    bar_parser.add_argument(
        "--sort",
        choices=["asc", "desc"],
        default="desc",
        help="Sort bars by GPU hours ascending or descending (defaults to desc).",
    )
    bar_parser.add_argument(
        "--norm",
        type=_parse_bool,
        default=False,
        help="Normalize GPU hours by the total and plot percentages (true/false).",
    )
    bar_parser.add_argument(
        "--n",
        type=int,
        help="Plot only the first N projects after sorting.",
    )

    return parser


def handle_horizontal_bar_chart(args: argparse.Namespace) -> str:
    csv_content = _read_csv_content(args.input)
    records = _load_gpu_hours(csv_content)
    aggregated = _aggregate_gpu_hours(records)
    ordered = _sort_and_trim(aggregated, args.sort, args.n)

    plot_gpu_hours_horizontal_bar(
        ordered,
        normalized=args.norm,
        sort_order=args.sort,
        output_path=args.output,
    )

    return args.output


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "horizontal-bar-chart-gpuhours":
        output = handle_horizontal_bar_chart(args)
    else:  # pragma: no cover - argparse enforces known commands
        parser.error("Unknown command")
        return

    print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
