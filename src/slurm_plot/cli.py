"""Command-line interface for SLURM plotting utilities."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
import math
from pathlib import Path
from typing import Iterable, Sequence

from .output import (
    BarChartData,
    HeatmapData,
    plot_gpu_hours_donut_chart,
    plot_gpu_hours_heatmap,
    plot_gpu_hours_horizontal_bar,
)


@dataclass(frozen=True)
class GpuHoursRecord:
    account: str
    gpu_hours: float


@dataclass(frozen=True)
class DssUsageRecord:
    project: str
    assigned_gb: str
    used_gb: str


@dataclass(frozen=True)
class ProjectListRecord:
    project_id: str
    partner: str
    institution: str


def _parse_bool(value: str) -> bool:
    value_lower = value.strip().lower()
    if value_lower in {"true", "1", "yes", "y"}:
        return True
    if value_lower in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean value (true/false).")


def _parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected a positive integer.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer.")
    return parsed


def _read_csv_content(input_path: str | None) -> str:
    if input_path:
        with open(input_path, "r", encoding="utf-8") as handle:
            return handle.read()

    if sys.stdin.isatty():
        raise SystemExit("Provide --input or pipe CSV data via stdin.")

    return sys.stdin.read()


def _load_gpu_hours_rows(csv_content: str) -> tuple[list[dict[str, str]], str | None]:
    reader = csv.DictReader(StringIO(csv_content))
    if reader.fieldnames is None:
        raise SystemExit("CSV data is missing headers.")

    required_fields = {"account", "gpu_hours"}
    if not required_fields.issubset(set(reader.fieldnames)):
        missing = ", ".join(sorted(required_fields.difference(set(reader.fieldnames))))
        raise SystemExit(f"CSV data missing required columns: {missing}")

    window_field = next(
        (field for field in reader.fieldnames if field not in required_fields),
        None,
    )
    rows = list(reader)
    latest_window = None
    if window_field:
        latest_window = _select_latest_window(rows, window_field)
        if latest_window:
            rows = [
                row
                for row in rows
                if row.get(window_field, "").strip() == latest_window
            ]

    return rows, latest_window


def _load_gpu_hours(csv_content: str) -> list[GpuHoursRecord]:
    rows, _ = _load_gpu_hours_rows(csv_content)

    records: list[GpuHoursRecord] = []
    for row in rows:
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


def _load_gpu_hours_with_window(
    csv_content: str,
) -> tuple[list[GpuHoursRecord], str | None]:
    rows, latest_window = _load_gpu_hours_rows(csv_content)
    records: list[GpuHoursRecord] = []
    for row in rows:
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

    return records, latest_window


def _parse_window_end(window: str) -> datetime | None:
    if not window:
        return None
    end_segment = window.split("..")[-1].strip()
    for pattern in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(end_segment, pattern)
        except ValueError:
            continue
    return None


def _select_latest_window(rows: list[dict[str, str]], window_field: str) -> str | None:
    window_values = [
        str(row.get(window_field, "")).strip() for row in rows if row.get(window_field, "")
    ]
    if not window_values:
        return None

    def _window_key(value: str) -> tuple[int, datetime, str]:
        parsed = _parse_window_end(value)
        if parsed is None:
            return (0, datetime.min, value)
        return (1, parsed, value)

    return max(window_values, key=_window_key)


def _parse_quarter_start(window: str) -> datetime | None:
    if not window:
        return None
    start_segment = window.split("..")[0].strip()
    for pattern in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(start_segment, pattern)
        except ValueError:
            continue
    return None


def _format_quarter_label(window: str) -> str:
    parsed = _parse_quarter_start(window)
    if parsed is None:
        return window
    quarter = ((parsed.month - 1) // 3) + 1
    return f"{parsed.year} Q{quarter}"


def _quarter_sort_key(window: str) -> tuple[int, datetime, str]:
    parsed = _parse_quarter_start(window)
    if parsed is None:
        return (1, datetime.max, window)
    return (0, parsed, window)


def _load_gpu_hours_heatmap(csv_content: str) -> HeatmapData:
    reader = csv.DictReader(StringIO(csv_content))
    if reader.fieldnames is None:
        raise SystemExit("CSV data is missing headers.")

    fieldnames = set(reader.fieldnames)
    if "gpu_hours" not in fieldnames:
        raise SystemExit("CSV data missing required columns: gpu_hours")

    if "user" in fieldnames:
        entity_field = "user"
        entity_label = "user"
    elif "account" in fieldnames:
        entity_field = "account"
        entity_label = "project"
    else:
        raise SystemExit("CSV data missing required columns: account or user")

    quarter_field = next(
        (
            field
            for field in ("quarter", "3months")
            if field in fieldnames
        ),
        None,
    )
    if quarter_field is None:
        remaining_fields = [
            field
            for field in reader.fieldnames
            if field not in {entity_field, "gpu_hours"}
        ]
        quarter_field = remaining_fields[0] if remaining_fields else None
    if quarter_field is None:
        raise SystemExit("CSV data missing required columns: quarter")

    totals: dict[tuple[str, str], float] = defaultdict(float)
    entity_totals: dict[str, float] = defaultdict(float)
    quarters_seen: set[str] = set()

    for row in reader:
        quarter = str(row.get(quarter_field, "")).strip()
        entity = str(row.get(entity_field, "")).strip()
        if not quarter or not entity:
            continue
        try:
            gpu_hours = float(row.get("gpu_hours", 0) or 0)
        except ValueError as exc:
            raise SystemExit(f"Invalid gpu_hours value: {row.get('gpu_hours')}") from exc

        totals[(entity, quarter)] += gpu_hours
        entity_totals[entity] += gpu_hours
        quarters_seen.add(quarter)

    if not totals:
        raise SystemExit("No valid rows found in the CSV data.")

    quarters = sorted(quarters_seen, key=_quarter_sort_key)
    entities = sorted(entity_totals, key=lambda item: (-entity_totals[item], item))
    values = [
        [totals.get((entity, quarter), 0.0) for quarter in quarters]
        for entity in entities
    ]

    return HeatmapData(
        row_labels=entities,
        column_labels=[_format_quarter_label(quarter) for quarter in quarters],
        values=values,
        entity_label=entity_label,
    )

def _load_gpu_hours_by_project(input_path: str, *, ignore_default: bool) -> dict[str, float]:
    with open(input_path, "r", encoding="utf-8") as handle:
        csv_content = handle.read()
    records = _load_gpu_hours(csv_content)
    totals: dict[str, float] = defaultdict(float)
    for record in records:
        if ignore_default and record.account == "default":
            continue
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


def _load_project_list(input_path: str) -> dict[str, ProjectListRecord]:
    with open(input_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("Project list CSV data is missing headers.")

        required_fields = {"ProjectID", "Partner", "Institution"}
        if not required_fields.issubset(set(reader.fieldnames)):
            missing = ", ".join(sorted(required_fields.difference(set(reader.fieldnames))))
            raise SystemExit(f"Project list CSV data missing required columns: {missing}")

        records: dict[str, ProjectListRecord] = {}
        for row in reader:
            project_id = str(row.get("ProjectID", "")).strip()
            if not project_id:
                continue
            records[project_id] = ProjectListRecord(
                project_id=project_id,
                partner=str(row.get("Partner", "")).strip(),
                institution=str(row.get("Institution", "")).strip(),
            )

    return records




def _sum_gpuh(input_path: str) -> float:
    with open(input_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit("GPU hour CSV data is missing headers.")

        required_fields = {"gpu_hours"}
        if not required_fields.issubset(set(reader.fieldnames)):
            missing = ", ".join(sorted(required_fields.difference(set(reader.fieldnames))))
            raise SystemExit(f"GPU hour CSV data missing required columns: {missing}")

        total = 0.0
        for row in reader:
            raw_value = str(row.get("gpu_hours", "")).strip()
            if not raw_value:
                continue
            try:
                total += float(raw_value)
            except ValueError as exc:
                raise SystemExit(f"Invalid gpu_hours value: {raw_value}") from exc

    return total


def _combine_gpuh_info(
    gpuh_files: list[str],
    gpuh_col_headers: list[str],
    *,
    project_list_path: str | None,
    institution: str | None,
) -> str:
    if len(gpuh_files) != len(gpuh_col_headers):
        raise SystemExit("--gpuh-files and --gpuh-col-header must have the same number of items.")

    project_mapping = _load_project_list(project_list_path) if project_list_path else {}
    target_institution = institution.strip() if institution else ""

    per_project: dict[tuple[str, str], dict[str, str]] = {}
    for index, input_path in enumerate(gpuh_files):
        header = gpuh_col_headers[index]
        with open(input_path, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise SystemExit("GPU hour CSV data is missing headers.")

            required_fields = {"year", "account", "gpu_hours"}
            if not required_fields.issubset(set(reader.fieldnames)):
                missing = ", ".join(sorted(required_fields.difference(set(reader.fieldnames))))
                raise SystemExit(f"GPU hour CSV data missing required columns: {missing}")

            for row in reader:
                year = str(row.get("year", "")).strip()
                account = str(row.get("account", "")).strip()
                gpu_hours = str(row.get("gpu_hours", "")).strip()
                if not year or not account:
                    continue

                key = (year, account)
                if key not in per_project:
                    per_project[key] = {
                        "year": year,
                        "ProjectID": account,
                        "Partner": "",
                        **{name: "" for name in gpuh_col_headers},
                    }
                per_project[key][header] = gpu_hours

    rows = list(per_project.values())
    if project_mapping:
        for row in rows:
            metadata = project_mapping.get(row["ProjectID"])
            row["Partner"] = metadata.partner if metadata else ""

        if target_institution:
            rows = [
                row
                for row in rows
                if row["ProjectID"] in project_mapping
                and project_mapping[row["ProjectID"]].institution == target_institution
            ]

    rows.sort(key=lambda item: (item["year"], item["ProjectID"]))

    output = StringIO()
    fieldnames = ["year", "ProjectID", "Partner", *gpuh_col_headers]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().strip()


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

    heatmap_parser = subparsers.add_parser(
        "heatmap-gpuhours",
        help="Plot a quarterly GPU-hour heatmap by project or user.",
    )
    heatmap_parser.add_argument(
        "--input",
        type=str,
        help="Path to a CSV file with quarter/3months, account/user, and gpu_hours columns (defaults to stdin).",
    )
    heatmap_parser.add_argument(
        "--output",
        type=str,
        default="heatmap-gpuh.png",
        help="Output path for the heatmap image (PNG or PDF; defaults to heatmap-gpuh.png).",
    )
    heatmap_parser.add_argument(
        "--bin",
        type=_parse_positive_int,
        default=2000,
        help="GPU-hour bin size for discrete heatmap colors (defaults to 2000 GPUh).",
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
        "--ignore-default",
        type=_parse_bool,
        default=True,
        help="Ignore the default account when summarizing GPU hours (true/false).",
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

    combined_gpuh_parser = subparsers.add_parser(
        "combine-GPUh-info",
        help="Combine multiple GPU hour CSV files into a single CSV by year and project.",
    )
    combined_gpuh_parser.add_argument(
        "--gpuh-files",
        type=str,
        required=True,
        help="Comma-separated list of GPU hour CSV files.",
    )
    combined_gpuh_parser.add_argument(
        "--gpuh-col-header",
        type=str,
        required=True,
        help="Comma-separated output column names corresponding to --gpuh-files.",
    )
    combined_gpuh_parser.add_argument(
        "--project-list",
        type=str,
        help="Optional CSV mapping with ProjectID, Partner, Institution columns.",
    )
    combined_gpuh_parser.add_argument(
        "--institution",
        type=str,
        help="Optional institution name to filter projects (requires --project-list).",
    )

    sum_gpuh_parser = subparsers.add_parser(
        "sum-GPUh",
        help="Sum GPU hours from a year,account,gpu_hours CSV file.",
    )
    sum_gpuh_parser.add_argument(
        "--gpuh-file",
        type=str,
        required=True,
        help="Path to a GPU hour CSV file.",
    )

    return parser


def handle_horizontal_bar_chart(args: argparse.Namespace) -> str:
    csv_content = _read_csv_content(args.input)
    records, latest_window = _load_gpu_hours_with_window(csv_content)
    aggregated = _aggregate_gpu_hours(records, ignore_default=args.ignore_default)
    ordered = _sort_and_trim(aggregated, args.sort, args.n)
    title = args.title if args.title is not None else latest_window

    plot_gpu_hours_horizontal_bar(
        ordered,
        normalized=args.norm,
        sort_order=args.sort,
        title=title,
        output_path=args.output,
    )

    return args.output


def handle_donut_chart(args: argparse.Namespace) -> str:
    csv_content = _read_csv_content(args.input)
    records, latest_window = _load_gpu_hours_with_window(csv_content)
    aggregated = _aggregate_gpu_hours(records, ignore_default=args.ignore_default)
    ordered = _sort_and_trim(aggregated, "desc", None)
    title = args.title if args.title is not None else latest_window
    output_path = Path(args.output)
    if output_path.parent != Path("."):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_gpu_hours_donut_chart(
        ordered,
        normalized=args.norm,
        title=title,
        output_path=str(output_path),
    )

    return str(output_path)


def handle_heatmap_gpuhours(args: argparse.Namespace) -> str:
    csv_content = _read_csv_content(args.input)
    heatmap_data = _load_gpu_hours_heatmap(csv_content)
    output_path = Path(args.output)
    if output_path.parent != Path("."):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    plot_gpu_hours_heatmap(
        heatmap_data,
        output_path=str(output_path),
        bin_size=args.bin,
    )

    return str(output_path)


def handle_project_information(args: argparse.Namespace) -> str:
    pi_mapping = _load_project_pi(args.input_pi) if args.input_pi else {}
    gpu_hours_mapping = {}
    if args.input_gpuh:
        gpu_hours_mapping = _load_gpu_hours_by_project(
            args.input_gpuh,
            ignore_default=getattr(args, "ignore_default", True),
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
    elif args.command == "heatmap-gpuhours":
        output = handle_heatmap_gpuhours(args)
    elif args.command == "project-information":
        output = handle_project_information(args)
    elif args.command == "combine-GPUh-info":
        gpuh_files = [item.strip() for item in args.gpuh_files.split(",") if item.strip()]
        gpuh_col_headers = [
            item.strip() for item in args.gpuh_col_header.split(",") if item.strip()
        ]
        output = _combine_gpuh_info(
            gpuh_files,
            gpuh_col_headers,
            project_list_path=args.project_list,
            institution=args.institution,
        )
    elif args.command == "sum-GPUh":
        output = str(_sum_gpuh(args.gpuh_file))
    else:  # pragma: no cover - argparse enforces known commands
        parser.error("Unknown command")
        return

    print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
