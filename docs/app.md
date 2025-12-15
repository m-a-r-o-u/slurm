# slurm app

Opinionated applications built on the utilities. The entry point is `slurm app`.

## GPU hours per project

Aggregate GPU-hours per project for a given partition. Provide job payloads as JSON strings or use the built-in demo dataset.

```
slurm app gpu-hours-per-project -p <PARTITION> ["{...job json...}" ...]
```

Each job JSON requires:

- `project`
- `job_id`
- `gpus`
- `hours_per_day`
- `start`
- `end`

Example using demo data on partition `gpu`:

```
slurm app gpu-hours-per-project -p gpu
```

Example output:

```
[
  {
    "project": "research",
    "partition": "gpu",
    "jobs": [
      {"project": "research", "job_id": "12345", "gpus": 2, "hours_per_day": 24.0, "start": "2024-01-01", "end": "2024-01-15", "gpu_hours": 720.0},
      {"project": "research", "job_id": "12346", "gpus": 1, "hours_per_day": 12.0, "start": "2024-02-01", "end": "2024-02-29", "gpu_hours": 348.0}
    ],
    "total_gpu_hours": 1068.0
  },
  {
    "project": "product",
    "partition": "gpu",
    "jobs": [
      {"project": "product", "job_id": "22345", "gpus": 4, "hours_per_day": 8.0, "start": "2024-01-01", "end": "2024-12-31", "gpu_hours": 11648.0}
    ],
    "total_gpu_hours": 11648.0
  }
]
```
