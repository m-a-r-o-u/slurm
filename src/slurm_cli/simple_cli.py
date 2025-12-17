"""Simplified command-line interface for common SLURM utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .cli import _add_date_arguments, _resolve_date_range_from_args
from .exports import export_sacct


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


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "export-sacct":
        output = handle_export_sacct(args)
    else:  # pragma: no cover - argparse enforces known commands
        parser.error("Unknown command")
        return

    print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
