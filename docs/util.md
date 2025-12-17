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

- The command is idempotent: rerunning it rewrites `jobs_data.parquet` from the current CSV files.
- Derived fields include waiting time, GPU hours, GPU/CPU counts, and convenience booleans (`is_gpu_job`, `is_failed`, `is_wasted`).
- Timestamp columns are parsed to UTC, and date buckets are derived from the end timestamp (or submit time when missing).
- When PyArrow is unavailable the dataset is written as JSON to the same path for portability in constrained environments.

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
