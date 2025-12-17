# SLURM CLI

A lightweight command-line toolkit with two layers:

- **slurm utils**: foundational, reusable calculations and exports (e.g., GPU-hour math, sacct CSV dumps).
- **slurm app**: opinionated workflows built on the utilities for reporting.

## Quickstart

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
slurm --help
```

## Documentation

- [Utility commands](docs/util.md)
- [Application workflows](docs/app.md)
