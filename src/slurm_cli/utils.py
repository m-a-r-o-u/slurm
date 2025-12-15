"""Utility helpers for SLURM calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .dates import DateRange


@dataclass
class JobUsage:
    """Represents GPU usage for a job over a date range."""

    job_id: str
    gpus: int
    hours_per_day: float
    date_range: DateRange
    project: str | None = None

    @property
    def gpu_hours(self) -> float:
        return self.hours_per_day * self.gpus * self.date_range.days()

    def as_dict(self) -> dict[str, str | float | int]:
        return {
            "job_id": self.job_id,
            "gpus": self.gpus,
            "hours_per_day": self.hours_per_day,
            "start": self.date_range.start.isoformat(),
            "end": self.date_range.end.isoformat(),
            "project": self.project or "unknown",
            "gpu_hours": round(self.gpu_hours, 2),
        }


def calculate_job_gpu_hours(
    job_id: str,
    date_range: DateRange,
    gpus: int = 1,
    hours_per_day: float = 24.0,
    project: str | None = None,
) -> JobUsage:
    """Calculate GPU hours for a job given a date range.

    Args:
        job_id: Identifier for the job.
        date_range: Inclusive date range for the job run.
        gpus: Number of GPUs allocated per job run. Defaults to 1.
        hours_per_day: Total hours per day the job is assumed to run. Defaults to 24.
    """

    if gpus <= 0:
        raise ValueError("GPU count must be positive.")
    if hours_per_day <= 0:
        raise ValueError("Hours per day must be positive.")

    return JobUsage(
        job_id=job_id,
        gpus=gpus,
        hours_per_day=hours_per_day,
        date_range=date_range,
        project=project,
    )


def summarize_gpu_hours_per_project(projects: dict[str, list[JobUsage]]) -> dict[str, float]:
    """Aggregate GPU hours per project from job usage records."""

    totals: dict[str, float] = {}
    for project, jobs in projects.items():
        totals[project] = round(sum(job.gpu_hours for job in jobs), 2)
    return totals
