"""Export helpers for SLURM tooling."""

from __future__ import annotations

import csv
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterable

from .dates import DateRange

SACCT_FIELDS = [
    "JobIDRaw",
    "User",
    "Account",
    "Partition",
    "Submit",
    "Start",
    "End",
    "State",
    "ExitCode",
    "ElapsedRaw",
    "AllocTRES",
]


def _sacct_command(start: date, end: date) -> str:
    return (
        "sacct -a -X -s CA,CD,F,NF,PR,TO "
        f"-S {start.isoformat()} -E {end.isoformat()} "
        "--format=JobIDRaw,User,Account,Partition,Submit,Start,End,State,ExitCode,ElapsedRaw,AllocTRES "
        "--parsable2 --noheader --delimiter='|' "
        "| awk -F'|' '$6 != \"None\" && $10 > 0 && $11 != \"\"'"
    )


def _iter_days(date_range: DateRange) -> Iterable[date]:
    current = date_range.start
    while current <= date_range.end:
        yield current
        current += timedelta(days=1)


def export_sacct(
    *,
    date_range: DateRange,
    output_dir: Path,
    debug: bool = False,
    missing: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[Path]:
    """Export sacct data for each day in the date range to CSV files.

    Args:
        date_range: Inclusive range of dates to export.
        output_dir: Directory to write CSV files.
        debug: When True, print commands executed.
        missing: When True, skip days that already have exported CSV files.
        runner: Command execution function (defaults to subprocess.run).
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    for day in _iter_days(date_range):
        output_file = output_dir / f"{day.isoformat()}.csv"
        if missing and output_file.exists():
            continue

        command = _sacct_command(day, day + timedelta(days=1))
        if debug:
            print(f"[debug] {command}")
        result = runner(command, shell=True, check=True, capture_output=True, text=True)
        with output_file.open("w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(SACCT_FIELDS)
            for line in result.stdout.splitlines():
                if line.strip():
                    writer.writerow(line.split("|"))

        generated.append(output_file)

    return generated
