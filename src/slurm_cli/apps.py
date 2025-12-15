"""Higher-level SLURM applications built on utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .utils import JobUsage, summarize_gpu_hours_per_project


@dataclass
class ProjectPartitionUsage:
    """GPU hours associated with a partition within a project."""

    project: str
    partition: str
    jobs: list[JobUsage]

    def total_gpu_hours(self) -> float:
        return summarize_gpu_hours_per_project({self.project: self.jobs})[self.project]


def report_gpu_hours_by_project(partition: str, project_jobs: dict[str, Iterable[JobUsage]]) -> list[ProjectPartitionUsage]:
    """Create summaries of GPU hours per project for a specific partition."""

    results: list[ProjectPartitionUsage] = []
    for project, jobs in project_jobs.items():
        results.append(ProjectPartitionUsage(project=project, partition=partition, jobs=list(jobs)))
    return results
