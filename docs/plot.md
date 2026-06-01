# slurm-plot

`slurm-plot` contains plotting and reporting helpers for CSV outputs produced by the
SLURM utility commands. It is installed as a separate command-line entry point:

```bash
slurm-plot --help
```

> Note: the plotting command is `slurm-plot` with a hyphen. It is not currently a
> nested `slurm plot` subcommand.

## Command-line shape

```text
slurm-plot <command> [options]
```

Available commands:

| Command | Purpose |
| --- | --- |
| `horizontal-bar-chart-gpuhours` | Plot GPU hours per project as a horizontal bar chart. |
| `donut-chart-gpuhours` | Plot GPU hours per project as a donut chart. |
| `heatmap-gpuhours` | Plot quarterly GPU hours by project/account or user as a heatmap. |
| `project-information` | Generate a project information table from PI, GPU-hour, and DSS inputs. |
| `combine-GPUh-info` | Combine multiple GPU-hour CSV files into one CSV by year and project. |
| `sum-GPUh` | Sum the `gpu_hours` column in a GPU-hour CSV file. |

Run help for any command to see all options:

```bash
slurm-plot horizontal-bar-chart-gpuhours --help
slurm-plot donut-chart-gpuhours --help
slurm-plot heatmap-gpuhours --help
slurm-plot project-information --help
slurm-plot combine-GPUh-info --help
slurm-plot sum-GPUh --help
```

## Input CSV format for GPU-hour charts

The chart commands read CSV from `--input` or from standard input. The CSV must
include at least these columns:

- `account`: project or account name to show in the chart.
- `gpu_hours`: numeric GPU-hour value.

A date/window column such as `year`, `month`, or `window` is optional. When one
extra column is present, `slurm-plot` automatically selects the latest window and
uses that window as the chart title when `--title` is omitted.

Example `gpuh.csv`:

```csv
year,account,gpu_hours
2024,research,1488
2024,product,320
2024,default,10
```

Rows whose `account` value contains comma-separated account names are split and
counted for each account. By default, the `default` account is ignored in charts;
pass `--ignore-default false` to include it.

## Horizontal bar chart

Use this when you want a sorted comparison of projects or accounts.

```bash
slurm-plot horizontal-bar-chart-gpuhours \
  --input gpuh.csv \
  --output gpu-hours.png \
  --sort desc \
  --n 20 \
  --title 2024
```

Common options:

- `--input PATH`: CSV file to read. If omitted, CSV is read from stdin.
- `--output PATH`: image file to write. Defaults to `gpu-hours.png`.
- `--sort asc|desc`: sort by GPU hours. Defaults to `desc`.
- `--n N`: keep only the first `N` projects after sorting.
- `--norm true|false`: plot percentages instead of raw GPU hours.
- `--ignore-default true|false`: exclude or include the `default` account.
  Defaults to `true`.
- `--title TEXT`: optional title suffix. If omitted and the CSV has a window
  column, the latest window is used.

You can also pipe CSV into the command:

```bash
slurm-utils metrics query gpu_hours --by year,account --format csv \
  | slurm-plot horizontal-bar-chart-gpuhours --output gpu-hours.png
```

## Donut chart

Use this when you want a part-of-total view of GPU hours.

```bash
slurm-plot donut-chart-gpuhours \
  --input gpuh.csv \
  --output gpu-hours-donut.png \
  --norm true \
  --title 2024
```

Common options:

- `--input PATH`: CSV file to read. If omitted, CSV is read from stdin.
- `--output PATH`: image file to write. Defaults to `gpu-hours-donut.png`.
- `--norm true|false`: show percentages instead of raw GPU hours.
- `--ignore-default true|false`: exclude or include the `default` account.
  Defaults to `true`.
- `--title TEXT`: optional title suffix. If omitted and the CSV has a window
  column, the latest window is used.

## Quarterly GPU-hour heatmap

Use `heatmap-gpuhours` to visualize GPU usage over time. The command accepts
CSV input with a quarter/window column (`quarter`, `3months`, or the remaining
non-ID column), either `account` for projects or `user` for users, and
`gpu_hours`. It sorts projects or users by total GPU hours descending, preserves
chronological quarter order, and fills missing project-quarter or user-quarter
combinations with `0`.

```bash
slurm-plot heatmap-gpuhours \
  --input gpuh.csv \
  --output heatmap-gpuh.pdf \
  --bin 2000
```

Example project input:

```csv
3months,account,gpu_hours
2025-01..2025-03,b2101,0.2
2025-01..2025-03,bx121,0.0
2025-04..2025-06,b2101,5001
```

Example user input:

```csv
3months,user,gpu_hours
2025-01..2025-03,apdl006,143.2
2025-01..2025-03,apdl011,466.6
```

The output format follows the `--output` file extension; use `.png` for PNG or
`.pdf` for PDF. Cells use discrete GPU-hour color bins, include exact GPU-hour
values, and show a bin legend. Use `--bin` to set the bin size in GPUh; the
default is `2000`. Quarter labels are shown on both the top and bottom axes for
readability.

## Project information table

`project-information` joins available project metadata into one table. Provide at
least one input file.

```bash
slurm-plot project-information \
  --input-pi project-pis.txt \
  --input-gpuh gpuh.csv \
  --input-dss dss.csv \
  --output project-information.md \
  --format markdown
```

Accepted inputs:

- `--input-pi PATH`: whitespace-delimited text file where the first token is the
  project ID and the rest of the line is the PI name.
- `--input-gpuh PATH`: CSV with `account` and `gpu_hours` columns. A `year` or
  other window column may also be present.
- `--input-dss PATH`: CSV with `Project`, `Assigned GB`, and `Used GB` columns.

Output formats are `csv`, `table`, and `markdown`. The default output file is
`project-information.csv`.

## Combine GPU-hour CSV files

Use `combine-GPUh-info` to align multiple GPU-hour CSV exports into a single CSV.
The result is written to stdout.

```bash
slurm-plot combine-GPUh-info \
  --gpuh-files gpu-a100.csv,gpu-h100.csv \
  --gpuh-col-header A100,H100 \
  --project-list projects.csv \
  --institution "Example University" > combined-gpuh.csv
```

Input GPU-hour files must contain `year`, `account`, and `gpu_hours` columns.
When `--project-list` is provided, it must be a CSV with `ProjectID`, `Partner`,
and `Institution` columns. `--institution` filters the combined output to one
institution and requires `--project-list`.

## Sum GPU hours

Use `sum-GPUh` for a quick total of the `gpu_hours` column:

```bash
slurm-plot sum-GPUh --gpuh-file gpuh.csv
```

The command prints a single numeric total to stdout.
