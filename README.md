# SLURM CLI

A lightweight command-line toolkit with reusable SLURM utilities, opinionated application workflows, and plotting helpers.

The package installs three command-line entry points:

- **`slurm`**: nested command with `utils` and `app` subcommands.
- **`slurm-utils`**: lean utility entry point for exports and metrics without nested `slurm utils` navigation.
- **`slurm-plot`**: plotting and CSV reporting helpers. Use this command for charts; there is no nested `slurm plot` command today.

## Quickstart

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
slurm --help
```

## Command-line overview

```text
slurm --help
slurm utils --help
slurm app --help
slurm-utils --help
slurm-plot --help
```

Common workflows:

```bash
# Export daily sacct CSV files.
slurm utils export sacct --date 2024-05 --output-dir sacct-exports

# Build and query an analytics dataset.
slurm-utils metrics build --input-dir sacct-exports --output-path metrics/jobs_data.parquet
slurm-utils metrics query gpu_hours --by year,account --format csv > gpuh.csv

# Plot the resulting GPU-hour CSV.
slurm-plot horizontal-bar-chart-gpuhours --input gpuh.csv --output gpu-hours.png
slurm-plot donut-chart-gpuhours --input gpuh.csv --output gpu-hours-donut.png --norm true
```

## Documentation

- [Utility commands](docs/util.md)
- [Application workflows](docs/app.md)
- [Plotting commands](docs/plot.md)
