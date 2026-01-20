"""Command-line interface for SLURM utilities and applications."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .apps import report_gpu_hours_by_project
from .dates import DateRange, DateRangeError, resolve_date_range
from .exports import export_sacct
from .utils import JobUsage, calculate_job_gpu_hours


def _add_date_arguments(parser: argparse.ArgumentParser, start_required: bool = True) -> None:
    group = parser.add_mutually_exclusive_group(required=start_required)
    group.add_argument(
        "--start",
        "-s",
        help=(
            "Start date in YYYY, YYYY-MM, or YYYY-MM-DD. When provided, you can optionally"
            " set --end to override the derived end date."
        ),
    )
    group.add_argument(
        "--date",
        "-d",
        help=(
            "Single date selector accepting YYYY, YYYY-MM, or YYYY-MM-DD. The precision"
            " determines the range: year → full year, month → full month, day → that day. "
            "Relative selectors include lastM:N for the last N months and lastD:N for the last N days."
        ),
    )
    parser.add_argument(
        "--end",
        "-e",
        help=(
            "Optional end date in YYYY-MM-DD. Ignored when --date is used. When omitted,"
            " the end date is derived from the --start precision."
        ),
    )


def _resolve_date_range_from_args(args: argparse.Namespace) -> DateRange:
    reference_date = getattr(args, "reference_date", None)
    if getattr(args, "date", None):
        date_value = str(args.date)
        try:
            return resolve_date_range(date_value, None, reference_date=reference_date)
        except DateRangeError as exc:  # noqa: TRY301
            raise SystemExit(str(exc))

    if getattr(args, "start", None):
        try:
            return resolve_date_range(
                str(args.start), getattr(args, "end", None), reference_date=reference_date
            )
        except DateRangeError as exc:  # noqa: TRY301
            raise SystemExit(str(exc))

    raise SystemExit("Provide either --date or --start to select a date range.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slurm",
        description=(
            "SLURM command-line tooling with reusable utilities and higher-level applications. "
            "Use 'slurm utils' for foundational helpers and 'slurm app' for composable workflows."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Utilities
    util_parser = subparsers.add_parser(
        "utils",
        help="Foundational helpers such as GPU-hour calculations and data exports.",
        description=(
            "Access reusable SLURM utilities. Pair flexible date selection with GPU-hour calculators "
            "or sacct CSV exports. Use subcommands to choose the workflow."
        ),
    )
    util_subparsers = util_parser.add_subparsers(dest="util_command", required=True)

    gpu_parser = util_subparsers.add_parser(
        "gpu-hours",
        help="Calculate GPU-hours for a SLURM job across a date range.",
        description=(
            "Provide a job ID and a date selector to estimate GPU-hours. The calculator"
            " accepts either an explicit start/end pair or a single --date value that"
            " expands to a full year, month, or day."
        ),
    )
    gpu_parser.add_argument("job_id", help="SLURM job identifier to describe.")
    _add_date_arguments(gpu_parser)
    gpu_parser.add_argument(
        "--gpus",
        type=int,
        default=1,
        help="Number of GPUs allocated to the job (defaults to 1).",
    )
    gpu_parser.add_argument(
        "--hours-per-day",
        type=float,
        default=24.0,
        help="Assumed runtime hours per day for the job (defaults to 24).",
    )

    export_parser = util_subparsers.add_parser(
        "export",
        help="Export data from SLURM tools such as sacct.",
        description=(
            "Generate CSV exports for SLURM data sources. Exports honor the same flexible"
            " date selectors used by other utilities."
        ),
    )
    export_subparsers = export_parser.add_subparsers(dest="export_command", required=True)

    sacct_parser = export_subparsers.add_parser(
        "sacct",
        help="Export sacct job accounting data to per-day CSV files.",
        description=(
            "Run sacct for each day in the selected range and write results to a"
            " sacct-exports/<YYYY-MM-DD>.csv file. Accepts a single --date selector or"
            " an explicit --start/--end pair."
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
    sacct_parser.add_argument(
        "--missing",
        action="store_true",
        help=(
            "Only export days that do not already have CSV files in the output directory."
        ),
    )

    # Applications
    app_parser = subparsers.add_parser(
        "app",
        help="Higher-level applications built on SLURM utilities.",
        description=(
            "Applications compose the core utilities into opinionated workflows. "
            "Use them when you want reports and rollups rather than raw calculations."
        ),
    )
    app_subparsers = app_parser.add_subparsers(dest="app_command", required=True)

    gpu_hours_parser = app_subparsers.add_parser(
        "gpu-hours-per-project",
        help="Summarize GPU hours per project for a partition.",
        description=(
            "Aggregate job usage into GPU-hour totals per project. Provide the partition and a "
            "list of job records to produce a concise report."
        ),
    )
    gpu_hours_parser.add_argument(
        "--partition",
        "-p",
        required=True,
        help="Cluster partition to report on (for context only).",
    )
    gpu_hours_parser.add_argument(
        "jobs",
        nargs="*",
        help=(
            "Optional JSON strings describing jobs (job_id,gpus,hours_per_day,start,end). "
            "When omitted, a demo dataset is used."
        ),
    )

    return parser


def handle_utils_gpu_hours(args: argparse.Namespace) -> str:
    date_range = _resolve_date_range_from_args(args)

    usage = calculate_job_gpu_hours(
        job_id=args.job_id,
        date_range=date_range,
        gpus=args.gpus,
        hours_per_day=args.hours_per_day,
    )
    return json.dumps(usage.as_dict(), indent=2)


def handle_utils_export(args: argparse.Namespace) -> str:
    if args.export_command == "sacct":
        date_range = _resolve_date_range_from_args(args)
        generated = export_sacct(
            date_range=date_range,
            output_dir=args.output_dir,
            debug=args.debug,
            missing=args.missing,
        )
        return json.dumps(
            {
                "output_dir": str(args.output_dir),
                "files": [str(path) for path in generated],
                "days_exported": len(generated),
            },
            indent=2,
        )

    raise SystemExit("Unknown export command")


def _parse_job_json(value: str) -> JobUsage:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:  # noqa: B904
        raise SystemExit(f"Invalid job JSON: {exc}")

    required_fields = {"job_id", "gpus", "hours_per_day", "start", "end", "project"}
    if not required_fields.issubset(payload):
        missing = required_fields.difference(payload)
        raise SystemExit(f"Job payload missing fields: {', '.join(sorted(missing))}")

    try:
        date_range = resolve_date_range(str(payload["start"]), str(payload["end"]))
        return calculate_job_gpu_hours(
            job_id=str(payload["job_id"]),
            date_range=date_range,
            gpus=int(payload["gpus"]),
            hours_per_day=float(payload["hours_per_day"]),
            project=str(payload.get("project")),
        )
    except (ValueError, DateRangeError) as exc:
        raise SystemExit(str(exc))


def _demo_jobs() -> dict[str, list[JobUsage]]:
    return {
        "research": [
            calculate_job_gpu_hours(
                "12345",
                resolve_date_range("2024-01", "2024-01-15"),
                gpus=2,
                project="research",
            ),
            calculate_job_gpu_hours(
                "12346",
                resolve_date_range("2024-02", None),
                gpus=1,
                hours_per_day=12,
                project="research",
            ),
        ],
        "product": [
            calculate_job_gpu_hours(
                "22345",
                resolve_date_range("2024", None),
                gpus=4,
                hours_per_day=8,
                project="product",
            ),
        ],
    }


def handle_app(args: argparse.Namespace) -> str:
    if args.app_command == "gpu-hours-per-project":
        project_jobs: dict[str, list[JobUsage]] = {}
        if args.jobs:
            for raw in args.jobs:
                job = _parse_job_json(raw)
                project = job.as_dict().get("project", "unknown")
                project_jobs.setdefault(project, []).append(job)
        else:
            project_jobs = _demo_jobs()

        reports = report_gpu_hours_by_project(partition=args.partition, project_jobs=project_jobs)
        output = []
        for report in reports:
            output.append(
                {
                    "project": report.project,
                    "partition": report.partition,
                    "jobs": [job.as_dict() for job in report.jobs],
                    "total_gpu_hours": report.total_gpu_hours(),
                }
            )
        return json.dumps(output, indent=2)

    raise SystemExit("Unknown application command")


def handle_utils(args: argparse.Namespace) -> str:
    if args.util_command == "gpu-hours":
        return handle_utils_gpu_hours(args)
    if args.util_command == "export":
        return handle_utils_export(args)

    raise SystemExit("Unknown utility command")


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "utils":
        output = handle_utils(args)
    elif args.command == "app":
        output = handle_app(args)
    else:
        parser.error("Unknown command")
        return

    print(output)


if __name__ == "__main__":  # pragma: no cover
    main()
