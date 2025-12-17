"""Simplified command-line interface for common SLURM utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .cli import _add_date_arguments, _resolve_date_range_from_args
from .exports import export_sacct
from .metrics import update_metrics


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
            "Convert sacct CSV exports into analytics-ready Parquet datasets. Use the update "
            "subcommand to refresh jobs_data from the latest raw files."
        ),
    )
    metrics_subparsers = metrics_parser.add_subparsers(dest="metrics_command", required=True)

    metrics_update_parser = metrics_subparsers.add_parser(
        "update",
        help="Transform sacct CSV files into the jobs_data Parquet dataset.",
    )
    metrics_update_parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("sacct-exports"),
        help="Directory containing sacct CSV exports (defaults to ./sacct-exports).",
    )
    metrics_update_parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("metrics") / "jobs_data.parquet",
        help="Destination Parquet file for the jobs_data dataset (defaults to ./metrics/jobs_data.parquet).",
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


def handle_metrics_update(args: argparse.Namespace) -> str:
    result = update_metrics(input_dir=args.input_dir, output_path=args.output_path)
    return result.as_json()


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "export-sacct":
        output = handle_export_sacct(args)
    elif args.command == "metrics" and args.metrics_command == "update":
        output = handle_metrics_update(args)
    else:  # pragma: no cover - argparse enforces known commands
        parser.error("Unknown command")
        return

    print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
