# slurm utils

Foundational helpers for SLURM workflows. The entry point is `slurm utils`, which exposes GPU-hour calculations with flexible date ranges.

## GPU-hour calculator

```
slurm utils <JOBID> --start=<START_DATE> [--end=<END_DATE>] [--gpus N] [--hours-per-day H]
```

- `--start` is required and accepts `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`.
- `--end` is optional; when omitted it is derived from the `--start` precision.
- Date ranges are inclusive.

Example: calculate GPU hours for job `12345` starting May 2024 with 2 GPUs running 24 hours per day:

```
slurm utils 12345 --start=2024-05 --gpus 2
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
