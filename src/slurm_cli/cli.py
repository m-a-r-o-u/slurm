"""Command-line interface for SLURM utilities and applications."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .apps import report_gpu_hours_by_project
from .dates import DateRangeError, resolve_date_range
from .utils import JobUsage, calculate_job_gpu_hours


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
        help="Foundational helpers such as GPU-hour calculations.",
        description=(
            "Access reusable SLURM utilities. The GPU-hours calculator accepts flexible date ranges "
            "and returns a concise JSON payload for downstream processing."
        ),
    )
    util_parser.add_argument("job_id", help="SLURM job identifier to describe.")
    util_parser.add_argument(
        "--start",
        "-s",
        required=True,
        help=(
            "Start date in YYYY, YYYY-MM, or YYYY-MM-DD. Precision determines the default end date: "
            "year → last day of year, month → last day of month, day → last day of that month."
        ),
    )
    util_parser.add_argument(
        "--end",
        "-e",
        help="Optional end date in YYYY-MM-DD. When omitted, derived from the --start precision.",
    )
    util_parser.add_argument(
        "--gpus",
        type=int,
        default=1,
        help="Number of GPUs allocated to the job (defaults to 1).",
    )
    util_parser.add_argument(
        "--hours-per-day",
        type=float,
        default=24.0,
        help="Assumed runtime hours per day for the job (defaults to 24).",
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


def handle_utils(args: argparse.Namespace) -> str:
    try:
        date_range = resolve_date_range(args.start, args.end)
    except DateRangeError as exc:
        raise SystemExit(str(exc))

    usage = calculate_job_gpu_hours(
        job_id=args.job_id,
        date_range=date_range,
        gpus=args.gpus,
        hours_per_day=args.hours_per_day,
    )
    return json.dumps(usage.as_dict(), indent=2)


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
