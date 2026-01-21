"""Command-line interface for SLURM plotting utilities."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from io import StringIO
import math
from pathlib import Path
from typing import Iterable, Sequence

from .plots import BarChartData, plot_gpu_hours_donut_chart, plot_gpu_hours_horizontal_bar


@dataclass(frozen=True)
class GpuHoursRecord:
    account: str
    gpu_hours: float


@dataclass(frozen=True)
class DssUsageRecord:
    project: str
    assigned_gb: str
    used_gb: str


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
        accounts = [segment.strip() for segment in account.split(",") if segment.strip()]
        for account_name in accounts:
            records.append(GpuHoursRecord(account=account_name, gpu_hours=gpu_hours))

    if not records:
        raise SystemExit("No valid rows found in the CSV data.")

    return records


def _load_gpu_hours_by_project(input_path: str) -> dict[str, float]:
    with open(input_path, "r", encoding="utf-8") as handle:
        csv_content = handle.read()
    records = _load_gpu_hours(csv_content)
    totals: dict[str, float] = defaultdict(float)
    for record in records:
        totals[record.account] += record.gpu_hours
    return totals


def _round_hours(value: float) -> int:
    return int(math.floor(value + 0.5))


def _load_project_pi(input_path: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with open(input_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if not parts:
                continue
            project_id = parts[0]
            pi = " ".join(parts[1:]).strip()
            if pi.endswith(")") and "(" in pi:
                pi = pi.rsplit("(", 1)[0].strip()
            mapping[project_id] = pi if pi else "N/A"
    return mapping


def _load_dss_usage(input_path: str) -> dict[str, DssUsageRecord]:
    with open(input_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("DSS CSV data is missing headers.")

        required_fields = {"Project", "Assigned GB", "Used GB"}
        if not required_fields.issubset(set(reader.fieldnames)):
            missing = ", ".join(sorted(required_fields.difference(set(reader.fieldnames))))
            raise SystemExit(f"DSS CSV data missing required columns: {missing}")

        records: dict[str, DssUsageRecord] = {}
        for row in reader:
            project = str(row.get("Project", "")).strip()
            if not project:
                continue
            assigned = str(row.get("Assigned GB", "")).strip() or "N/A"
            used = str(row.get("Used GB", "")).strip() or "N/A"
            records[project] = DssUsageRecord(
                project=project,
                assigned_gb=assigned,
                used_gb=used,
            )

    return records


def _aggregate_gpu_hours(
    records: Iterable[GpuHoursRecord],
    *,
    ignore_default: bool,
) -> list[BarChartData]:
    totals: dict[str, float] = defaultdict(float)
    for record in records:
        if ignore_default and record.account == "default":
            continue
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
        "--ignore-default",
        type=_parse_bool,
        default=True,
        help="Ignore the default account when plotting (true/false).",
    )
    bar_parser.add_argument(
        "--n",
        type=int,
        help="Plot only the first N projects after sorting.",
    )
    bar_parser.add_argument(
        "--title",
        type=str,
        help="Optional title suffix to include in parentheses.",
    )

    donut_parser = subparsers.add_parser(
        "donut-chart-gpuhours",
        help="Plot a donut chart of GPU hours per project.",
    )
    donut_parser.add_argument(
        "--input",
        type=str,
        help="Path to a CSV file with year, account, and gpu_hours columns (defaults to stdin).",
    )
    donut_parser.add_argument(
        "--output",
        type=str,
        default="gpu-hours-donut.png",
        help="Output path for the chart image (defaults to gpu-hours-donut.png).",
    )
    donut_parser.add_argument(
        "--norm",
        type=_parse_bool,
        default=False,
        help="Normalize GPU hours by the total and plot percentages (true/false).",
    )
    donut_parser.add_argument(
        "--ignore-default",
        type=_parse_bool,
        default=True,
        help="Ignore the default account when plotting (true/false).",
    )
    donut_parser.add_argument(
        "--title",
        type=str,
        help="Optional title suffix to include in parentheses.",
    )

    info_parser = subparsers.add_parser(
        "project-information",
        help="Generate a project information table for PI, GPU hours, and DSS usage.",
    )
    info_parser.add_argument(
        "--input-pi",
        type=str,
        help="Path to a text file with project IDs and PI names.",
    )
    info_parser.add_argument(
        "--input-gpuh",
        type=str,
        help="Path to a CSV file with year, account, and gpu_hours columns.",
    )
    info_parser.add_argument(
        "--input-dss",
        type=str,
        help="Path to a CSV file with DSS storage columns.",
    )
    info_parser.add_argument(
        "--output",
        type=str,
        default="project-information.csv",
        help="Output path for the generated CSV table.",
    )
    info_parser.add_argument(
        "--format",
        choices=["csv", "table", "markdown"],
        default="csv",
        help="Output format for the project information (csv, table, markdown).",
    )

    return parser


def handle_horizontal_bar_chart(args: argparse.Namespace) -> str:
    csv_content = _read_csv_content(args.input)
    records = _load_gpu_hours(csv_content)
    aggregated = _aggregate_gpu_hours(records, ignore_default=args.ignore_default)
    ordered = _sort_and_trim(aggregated, args.sort, args.n)

    plot_gpu_hours_horizontal_bar(
        ordered,
        normalized=args.norm,
        sort_order=args.sort,
        title=args.title,
        output_path=args.output,
    )

    return args.output


def handle_donut_chart(args: argparse.Namespace) -> str:
    csv_content = _read_csv_content(args.input)
    records = _load_gpu_hours(csv_content)
    aggregated = _aggregate_gpu_hours(records, ignore_default=args.ignore_default)
    ordered = _sort_and_trim(aggregated, "desc", None)
    output_path = Path(args.output)
    if output_path.parent != Path("."):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_gpu_hours_donut_chart(
        ordered,
        normalized=args.norm,
        title=args.title,
        output_path=str(output_path),
    )

    return str(output_path)


def handle_project_information(args: argparse.Namespace) -> str:
    pi_mapping = _load_project_pi(args.input_pi) if args.input_pi else {}
    gpu_hours_mapping = (
        _load_gpu_hours_by_project(args.input_gpuh) if args.input_gpuh else {}
    )
    dss_mapping = _load_dss_usage(args.input_dss) if args.input_dss else {}

    if not (pi_mapping or gpu_hours_mapping or dss_mapping):
        raise SystemExit("Provide at least one input file.")

    project_ids = sorted(set(pi_mapping) | set(gpu_hours_mapping) | set(dss_mapping))

    header = ["ProjectID"]
    if args.input_pi:
        header.append("PI")
    if args.input_gpuh:
        header.append("GPU hours")
    if args.input_dss:
        header.extend(["DSS Assigned", "DSS Used"])

    with open(args.output, "w", encoding="utf-8", newline="") as handle:
        rows = []
        for project_id in project_ids:
            row = [project_id]
            if args.input_pi:
                row.append(pi_mapping.get(project_id, "N/A"))
            if args.input_gpuh:
                if project_id in gpu_hours_mapping:
                    row.append(str(_round_hours(gpu_hours_mapping[project_id])))
                else:
                    row.append("N/A")
            if args.input_dss:
                record = dss_mapping.get(project_id)
                if record:
                    row.extend([record.assigned_gb, record.used_gb])
                else:
                    row.extend(["N/A", "N/A"])
            rows.append(row)

        if args.format == "csv":
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        elif args.format == "markdown":
            handle.write("| " + " | ".join(header) + " |\n")
            handle.write("| " + " | ".join("---" for _ in header) + " |\n")
            for row in rows:
                handle.write("| " + " | ".join(row) + " |\n")
        else:
            widths = [len(column) for column in header]
            for row in rows:
                for index, value in enumerate(row):
                    widths[index] = max(widths[index], len(value))
            header_line = "  ".join(
                column.ljust(widths[index]) for index, column in enumerate(header)
            )
            handle.write(header_line + "\n")
            separator_line = "  ".join("-" * width for width in widths)
            handle.write(separator_line + "\n")
            for row in rows:
                line = "  ".join(
                    value.ljust(widths[index]) for index, value in enumerate(row)
                )
                handle.write(line + "\n")

    return args.output


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "horizontal-bar-chart-gpuhours":
        output = handle_horizontal_bar_chart(args)
    elif args.command == "donut-chart-gpuhours":
        output = handle_donut_chart(args)
    elif args.command == "project-information":
        output = handle_project_information(args)
    else:  # pragma: no cover - argparse enforces known commands
        parser.error("Unknown command")
        return

    print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
