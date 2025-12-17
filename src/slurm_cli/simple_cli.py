"""Simplified command-line interface for common SLURM utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .cli import _add_date_arguments, _resolve_date_range_from_args
from .exports import export_sacct
from .metrics import build_metrics, format_query_result, query_metrics


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slurm-utils",
        description=(
            "Lean interface for SLURM utility commands. Use 'export-sacct' to write per-day "
            "sacct CSV files without navigating nested subcommands."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    sacct_parser = subparsers.add_parser(
        "export-sacct",
        help="Export sacct job accounting data to per-day CSV files.",
        description=(
            "Run sacct for each day in the selected range and write results to a "
            "sacct-exports/<YYYY-MM-DD>.csv file. Accepts a single --date selector or "
            "an explicit --start/--end pair."
        ),
    )
    _add_date_arguments(sacct_parser)
    sacct_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("sacct-exports"),
        help="Directory to write per-day CSV files (defaults to ./sacct-exports).",
    )
    sacct_parser.add_argument(
        "--debug",
        action="store_true",
        help="Print the sacct commands executed for each day before running them.",
    )

    metrics_parser = subparsers.add_parser(
        "metrics",
        help="Maintain derived metrics datasets from raw exports.",
        description=(
            "Convert sacct CSV exports into analytics-ready Parquet datasets. Use the build "
            "subcommand to refresh jobs_data from the latest raw files."
        ),
    )
    metrics_subparsers = metrics_parser.add_subparsers(dest="metrics_command", required=True)

    metrics_build_parser = metrics_subparsers.add_parser(
        "build",
        help="Transform sacct CSV files into the jobs_data Parquet dataset.",
    )
    metrics_build_parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("sacct-exports"),
        help="Directory containing sacct CSV exports (defaults to ./sacct-exports).",
    )
    metrics_build_parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("metrics") / "jobs_data.parquet",
        help="Destination Parquet file for the jobs_data dataset (defaults to ./metrics/jobs_data.parquet).",
    )

    metrics_query_parser = metrics_subparsers.add_parser(
        "query",
        help="Aggregate metrics from the jobs_data dataset.",
    )
    metrics_query_parser.add_argument(
        "metric",
        help="Metric column to aggregate (e.g., gpu_hours).",
    )
    metrics_query_parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path("metrics") / "jobs_data.parquet",
        help="Path to the jobs_data dataset (defaults to ./metrics/jobs_data.parquet).",
    )
    metrics_query_parser.add_argument(
        "--by",
        type=str,
        default="",
        help=(
            "Comma-separated grouping columns. Supported: day, week, month, year, partition, "
            "account, user, state. At most one time-based value is allowed and it must be first."
        ),
    )
    metrics_query_parser.add_argument(
        "--stat",
        type=str,
        help="Statistic to apply (default: sum). Specify mean for per-job averages.",
    )
    _add_date_arguments(metrics_query_parser, start_required=False)
    metrics_query_parser.add_argument(
        "--format",
        choices=["json", "yaml", "table"],
        default="json",
        help="Output format for query results (json, yaml, table).",
    )

    return parser


def handle_export_sacct(args: argparse.Namespace) -> str:
    date_range = _resolve_date_range_from_args(args)
    generated = export_sacct(date_range=date_range, output_dir=args.output_dir, debug=args.debug)
    return json.dumps(
        {
            "output_dir": str(args.output_dir),
            "files": [str(path) for path in generated],
            "days_exported": len(generated),
        },
        indent=2,
    )


def handle_metrics_build(args: argparse.Namespace) -> str:
    result = build_metrics(input_dir=args.input_dir, output_path=args.output_path)
    return result.as_json()


def handle_metrics_query(args: argparse.Namespace) -> str:
    by_values = [entry.strip() for entry in (args.by or "").split(",") if entry.strip()]
    date_range = None
    if getattr(args, "date", None) or getattr(args, "start", None):
        date_range = _resolve_date_range_from_args(args)
    result = query_metrics(
        args.metric,
        dataset_path=args.dataset_path,
        by=by_values,
        stat=args.stat,
        date_range=date_range,
    )
    return format_query_result(result, output_format=args.format)


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "export-sacct":
        output = handle_export_sacct(args)
    elif args.command == "metrics" and args.metrics_command == "build":
        output = handle_metrics_build(args)
    elif args.command == "metrics" and args.metrics_command == "query":
        output = handle_metrics_query(args)
    else:  # pragma: no cover - argparse enforces known commands
        parser.error("Unknown command")
        return

    print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
