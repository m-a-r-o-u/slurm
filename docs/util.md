# slurm utils

Foundational helpers for SLURM workflows. The entry point is `slurm utils`, which now exposes GPU-hour calculations and sacct CSV exports with flexible date selectors.

## Date selection (shared across commands)

Every utility command accepts two ways to pick dates:

- `--date` (`-d`): a single value in `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` format. The precision expands to the full year, month, or day.
- `--start` (`-s`): an explicit start date (`YYYY`, `YYYY-MM`, or `YYYY-MM-DD`). You may provide `--end` to override the derived end date; otherwise it auto-expands based on the start precision.

Date ranges are inclusive when calculating totals, and sacct exports run for each day in the range.

## Metrics build

Turn sacct CSV exports into analytics-ready Parquet datasets:

```
slurm-utils metrics build --input-dir sacct-exports --output-path metrics/jobs_data.parquet
```

- The command is idempotent: rerunning it rewrites `jobs_data.parquet` (or `jobs_data.json` if Parquet is unavailable) from the current CSV files.
- Derived fields include waiting time, GPU hours, GPU/CPU counts, and convenience booleans (`is_gpu_job`, `is_failed`, `is_wasted`).
- Timestamp columns are parsed to UTC, and date buckets are derived from the end timestamp (or submit time when missing).
- When PyArrow is unavailable the dataset is written as JSON to a `.json` file for portability in constrained environments.

## Metrics query

Aggregate derived metrics from the jobs dataset:

```
slurm-utils metrics query gpu_hours --by month,account
slurm-utils metrics query gpu_hours --by month,account --stat mean
slurm-utils metrics query gpu_hours --date 2025-03 --format table
```

- `--by` sets grouping columns. Supported values: `day`, `week`, `month`, `year`, `partition`, `account`, `user`, `state`.
- At most one time-based value is allowed, and it must be the first entry. Time buckets are derived from `end_ts`.
- Statistics default to `sum`. Provide `--stat mean` for per-job averages (e.g., mean GPU hours per group).
- Optional date selectors `--date`, `--start`, and `--end` reuse the sacct export rules to limit which jobs to aggregate, based on `end_ts`.
- Use `--format` to switch output rendering: `json` (default), `yaml`, `csv`, or a plaintext `table` layout for quick inspection.
- Add `--select` to pre-filter jobs with shell-style patterns before aggregation. Supported keys: `partition`, `account`, `user`, `state`. Combine selectors with `;` in a single flag or repeat `--select` to AND multiple filters (e.g., `--select partition:mcml*;user:di38qex`).

## GPU-hour calculator

```
slurm utils gpu-hours <JOBID> (--date <DATE> | --start <START_DATE> [--end <END_DATE>]) [--gpus N] [--hours-per-day H]
```

Example: calculate GPU hours for job `12345` starting May 2024 with 2 GPUs running 24 hours per day:

```
slurm utils gpu-hours 12345 --start=2024-05 --gpus 2
```

Example output:

```
{
  "job_id": "12345",
  "gpus": 2,
  "hours_per_day": 24.0,
  "start": "2024-05-01",
  "end": "2024-05-31",
  "gpu_hours": 1488.0
}
```

## sacct export

Export daily sacct data to CSV files in `sacct-exports/`:

```
slurm utils export sacct --start YYYY-MM-DD --end YYYY-MM-DD
slurm utils export sacct --date YYYY-MM-DD
slurm utils export sacct --date YYYY-MM
slurm utils export sacct --date YYYY
```

- A CSV file is generated per day in the selected range, named `YYYY-MM-DD.csv`.
- Pass `--output-dir` to change the destination directory.
- Use `--debug` to print the exact sacct command executed per day before it runs.
