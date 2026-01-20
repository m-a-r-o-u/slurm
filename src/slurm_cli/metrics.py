"""Metrics pipeline for transforming sacct exports into analytics datasets."""
from __future__ import annotations

import csv
import json
import fnmatch
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .dates import DateRange


@dataclass(frozen=True)
class MetricsBuildResult:
    """Summary of a metrics build run."""

    source_files: list[Path]
    output_path: Path
    rows_written: int
    storage_format: str

    def as_json(self) -> str:
        return json.dumps(
            {
                "source_files": [str(path) for path in self.source_files],
                "output_path": str(self.output_path),
                "rows_written": self.rows_written,
                "storage_format": self.storage_format,
            },
            indent=2,
        )


@dataclass(frozen=True)
class MetricsQueryResult:
    """Result payload for an aggregated metrics query."""

    metric: str
    stat: str
    by: list[str]
    rows: list[dict]

    def as_json(self) -> str:
        return json.dumps(
            {
                "metric": self.metric,
                "stat": self.stat,
                "by": self.by,
                "rows": self.rows,
            },
            indent=2,
            default=str,
        )

    def as_dict(self) -> dict:
        return {
            "metric": self.metric,
            "stat": self.stat,
            "by": self.by,
            "rows": self.rows,
        }


@dataclass(frozen=True)
class AccountsWorkaroundResult:
    """Summary of the temporary account remapping workaround."""

    dataset_path: Path
    output_path: Path
    rows_scanned: int
    rows_updated: int
    users_remapped: list[str]
    storage_format: str

    def as_json(self) -> str:
        return json.dumps(
            {
                "dataset_path": str(self.dataset_path),
                "output_path": str(self.output_path),
                "rows_scanned": self.rows_scanned,
                "rows_updated": self.rows_updated,
                "users_remapped": self.users_remapped,
                "storage_format": self.storage_format,
            },
            indent=2,
        )


def _parse_dt(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError:
        return None


def _parse_int(value: str | None) -> int:
    try:
        return int(value) if value not in (None, "") else 0
    except ValueError:
        return 0


def _parse_elapsed(value: str | None) -> int:
    try:
        return int(float(value)) if value not in (None, "") else 0
    except ValueError:
        return 0


def _parse_mem_to_mb(value: str | None) -> int:
    if value is None or value == "":
        return 0
    raw = value.strip().upper()
    suffix = raw[-1]
    try:
        number = float(raw[:-1]) if suffix.isalpha() else float(raw)
    except ValueError:
        return 0

    if suffix == "T":
        return int(number * 1024 * 1024)
    if suffix == "G":
        return int(number * 1024)
    if suffix == "M":
        return int(number)
    return int(number)


def _parse_alloc_tres(value: str | None) -> dict[str, int]:
    gpu_count = cpu_count = node_count = billing_units = mem_req_mb = 0
    if not value:
        return {
            "gpu_count": gpu_count,
            "cpu_count": cpu_count,
            "node_count": node_count,
            "billing_units": billing_units,
            "mem_req_mb": mem_req_mb,
        }

    for item in value.split(","):
        if "=" not in item:
            continue
        key, raw_val = item.split("=", 1)
        key = key.strip().lower()
        raw_val = raw_val.strip()

        if key == "gres/gpu":
            gpu_count = _parse_int(raw_val)
        elif key == "cpu":
            cpu_count = _parse_int(raw_val)
        elif key == "node":
            node_count = _parse_int(raw_val)
        elif key == "billing":
            billing_units = _parse_int(raw_val)
        elif key == "mem":
            mem_req_mb = _parse_mem_to_mb(raw_val)

    return {
        "gpu_count": gpu_count,
        "cpu_count": cpu_count,
        "node_count": node_count,
        "billing_units": billing_units,
        "mem_req_mb": mem_req_mb,
    }


def _load_sacct_exports(paths: Iterable[Path]) -> List[dict]:
    records: list[dict] = []
    for path in sorted(paths):
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                row["__source_file"] = str(path)
                records.append(row)
    return records


def _derive_jobs(records: list[dict]) -> list[dict]:
    jobs: list[dict] = []
    for record in records:
        submit_ts = _parse_dt(record.get("Submit"))
        start_ts = _parse_dt(record.get("Start"))
        end_ts = _parse_dt(record.get("End"))

        elapsed_s = _parse_elapsed(record.get("ElapsedRaw"))
        wait_s = None
        if submit_ts and start_ts:
            wait_s = int((start_ts - submit_ts).total_seconds())

        alloc = _parse_alloc_tres(record.get("AllocTRES"))
        gpu_count = alloc.get("gpu_count", 0)

        date_key = end_ts.date() if end_ts else (submit_ts.date() if submit_ts else None)

        job = {
            "job_id": _parse_int(record.get("JobIDRaw")),
            "user_name": record.get("User"),
            "account": record.get("Account"),
            "partition": record.get("Partition"),
            "submit_ts": submit_ts,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "state": record.get("State"),
            "exit_code": record.get("ExitCode"),
            "elapsed_s": elapsed_s,
            "wait_s": wait_s,
            "gpu_count": gpu_count,
            "cpu_count": alloc.get("cpu_count", 0),
            "node_count": alloc.get("node_count", 0),
            "billing_units": alloc.get("billing_units", 0),
            "mem_req_mb": alloc.get("mem_req_mb", 0),
            "gpu_hours": (elapsed_s / 3600.0) * gpu_count,
            "is_gpu_job": gpu_count > 0,
            "is_failed": (record.get("State") or "").upper() != "COMPLETED",
            "is_wasted": gpu_count > 0 and (record.get("State") or "").upper() != "COMPLETED",
            "date_key": date_key,
            "submit_date": submit_ts.date() if submit_ts else None,
            "start_date": start_ts.date() if start_ts else None,
            "alloc_tres_raw": record.get("AllocTRES"),
            "__source_file": record.get("__source_file"),
        }
        jobs.append(job)
    return jobs


def _write_jobs_dataset(records: list[dict], output_path: Path) -> tuple[str, Path]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(records)
        pq.write_table(table, output_path)
        return "parquet", output_path
    except Exception:
        # Fallback to JSON when pyarrow is unavailable
        fallback_path = output_path
        if output_path.suffix == ".parquet":
            fallback_path = output_path.with_suffix(".json")
        fallback_path.write_text(json.dumps(records, default=str, indent=2))
        return "json", fallback_path


def _load_jobs_dataset(path: Path) -> list[dict]:
    if not path.exists():
        if path.suffix == ".parquet":
            fallback_path = path.with_suffix(".json")
            if fallback_path.exists():
                path = fallback_path
            else:
                raise FileNotFoundError(f"Dataset not found at {path}")
        else:
            fallback_path = path.with_suffix(".parquet")
            if fallback_path.exists():
                path = fallback_path
            else:
                raise FileNotFoundError(f"Dataset not found at {path}")

    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        return table.to_pylist()
    except Exception:
        payload = path.read_text(encoding="utf-8")
        return json.loads(payload)


def _resolve_jobs_dataset_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.suffix == ".parquet":
        fallback_path = path.with_suffix(".json")
        if fallback_path.exists():
            return fallback_path
    else:
        fallback_path = path.with_suffix(".parquet")
        if fallback_path.exists():
            return fallback_path
    return path


def _normalize_ts(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            ts = datetime.fromisoformat(value)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts
        except ValueError:
            return None
    return None


def _derive_time_bucket(end_ts: Optional[datetime], granularity: str) -> Optional[str]:
    if end_ts is None:
        return None

    if granularity == "day":
        return end_ts.date().isoformat()
    if granularity == "week":
        iso_year, iso_week, _ = end_ts.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if granularity == "month":
        return f"{end_ts.year:04d}-{end_ts.month:02d}"
    if granularity == "year":
        return f"{end_ts.year:04d}"
    return None


def _validate_grouping(by: list[str]) -> tuple[Optional[str], list[str]]:
    allowed = {"day", "week", "month", "year", "partition", "account", "user", "state"}
    time_keys = {"day", "week", "month", "year"}

    for entry in by:
        if entry not in allowed:
            raise ValueError(f"Unsupported grouping column: {entry}")

    time_in_by = [entry for entry in by if entry in time_keys]
    if len(time_in_by) > 1:
        raise ValueError("Only one time-based grouping is allowed and it must be first")
    time_prefix = time_in_by[0] if time_in_by else None
    if time_prefix and by and by[0] != time_prefix:
        raise ValueError("Time-based grouping must be the first entry in --by")

    return time_prefix, by


def _parse_selectors(select_args: Optional[Sequence[str]]) -> list[tuple[str, str]]:
    selectors: list[tuple[str, str]] = []
    if not select_args:
        return selectors

    allowed_keys = {"partition", "account", "user", "state"}

    for raw in select_args:
        if not raw:
            continue
        for entry in raw.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            if ":" not in entry:
                raise ValueError(f"Invalid selector '{entry}'. Expected key:pattern")
            key, pattern = entry.split(":", 1)
            key = key.strip().lower()
            pattern = pattern.strip()

            if key not in allowed_keys:
                raise ValueError(
                    f"Unsupported selector key '{key}'. Allowed: {', '.join(sorted(allowed_keys))}"
                )
            if pattern == "":
                raise ValueError("Selector pattern cannot be empty")

            selectors.append((key, pattern))

    return selectors


def _record_matches_selectors(
    record: dict, selectors: Sequence[tuple[str, str]], key_map: dict[str, str]
) -> bool:
    if not selectors:
        return True

    for key, pattern in selectors:
        record_key = key_map.get(key, key)
        value = record.get(record_key)
        if not fnmatch.fnmatch(str(value or ""), pattern):
            return False

    return True


def _is_in_date_range(end_ts: Optional[datetime], date_range: Optional[DateRange]) -> bool:
    if date_range is None:
        return True

    if end_ts is None:
        return False

    end_date = end_ts.date()
    return date_range.start <= end_date <= date_range.end


def query_metrics(
    metric: str,
    *,
    dataset_path: Path,
    by: Optional[list[str]] = None,
    stat: Optional[str] = None,
    date_range: Optional[DateRange] = None,
    selectors: Optional[Sequence[str]] = None,
) -> MetricsQueryResult:
    by = by or []
    stat = (stat or "sum").lower()
    if stat not in {"sum", "mean"}:
        raise ValueError(f"Unsupported statistic: {stat}")

    time_prefix, validated_by = _validate_grouping([entry.lower() for entry in by])
    parsed_selectors = _parse_selectors(selectors)
    records = _load_jobs_dataset(dataset_path)

    grouping_map = {
        "partition": "partition",
        "account": "account",
        "user": "user_name",
        "state": "state",
    }

    aggregates: dict[tuple, dict[str, float]] = {}

    for record in records:
        end_ts = _normalize_ts(record.get("end_ts"))
        if not _is_in_date_range(end_ts, date_range):
            continue
        if not _record_matches_selectors(record, parsed_selectors, grouping_map):
            continue

        metric_value = record.get(metric)
        if metric_value is None:
            continue
        try:
            numeric_value = float(metric_value)
        except (TypeError, ValueError):
            continue

        key_parts_options: list[list[object]] = []
        for group in validated_by:
            if group == time_prefix:
                key_parts_options.append([_derive_time_bucket(end_ts, group)])
                continue

            record_value = record.get(grouping_map.get(group, group))
            if group == "account" and record_value:
                account_values = [
                    segment.strip()
                    for segment in str(record_value).split(",")
                    if segment.strip()
                ]
                key_parts_options.append(account_values or [record_value])
            else:
                key_parts_options.append([record_value])

        keys: list[tuple[object, ...]] = [tuple()]
        for options in key_parts_options:
            keys = [existing + (option,) for existing in keys for option in options]

        for key in keys:
            if key not in aggregates:
                aggregates[key] = {"sum": 0.0, "count": 0}
            aggregates[key]["sum"] += numeric_value
            aggregates[key]["count"] += 1

    rows: list[dict] = []
    for key, values in aggregates.items():
        row: dict = {}
        for idx, group in enumerate(validated_by):
            row[group] = key[idx]
        if stat == "sum":
            row[metric] = values["sum"]
        elif stat == "mean":
            count = values["count"] or 1
            row[metric] = values["sum"] / count
        rows.append(row)

    rows.sort(key=lambda item: tuple(item.get(group) for group in validated_by))

    return MetricsQueryResult(metric=metric, stat=stat, by=validated_by, rows=rows)


def format_query_result(result: MetricsQueryResult, *, output_format: str = "json") -> str:
    output_format = output_format.lower()
    if output_format == "json":
        return result.as_json()
    if output_format == "yaml":
        import yaml

        return yaml.safe_dump(result.as_dict(), sort_keys=False)
    if output_format == "csv":
        columns = result.by + [result.metric]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        for row in result.rows:
            writer.writerow({column: row.get(column, "") for column in columns})
        return buffer.getvalue().strip()
    if output_format == "table":
        columns = result.by + [result.metric]
        widths: dict[str, int] = {}
        for column in columns:
            candidates = [len(column)]
            candidates.extend(len(str(row.get(column, ""))) for row in result.rows)
            widths[column] = max(candidates)

        header = " | ".join(column.ljust(widths[column]) for column in columns)
        separator = "-+-".join("-" * widths[column] for column in columns)

        lines = [header, separator]
        for row in result.rows:
            line = " | ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns)
            lines.append(line)

        return "\n".join(lines)

    raise ValueError(f"Unsupported format: {output_format}")


def build_metrics(*, input_dir: Path, output_path: Path) -> MetricsBuildResult:
    csv_files = sorted(input_dir.glob("*.csv"))
    raw_records = _load_sacct_exports(csv_files)
    jobs = _derive_jobs(raw_records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    storage_format, resolved_output_path = _write_jobs_dataset(jobs, output_path)

    return MetricsBuildResult(
        source_files=csv_files,
        output_path=resolved_output_path,
        rows_written=len(jobs),
        storage_format=storage_format,
    )


def _load_user_project_map(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            if row[0].startswith("#"):
                continue
            if len(row) < 2:
                continue
            user = row[0].strip()
            projects = row[1].strip()
            if user.lower() == "user_id" and projects.lower() == "projects":
                continue
            if not user or not projects:
                continue
            project_list = [project.strip() for project in projects.split("+") if project.strip()]
            if not project_list:
                continue
            mapping[user] = ",".join(project_list)
    return mapping


def apply_accounts_workaround(
    *,
    dataset_path: Path,
    mapping_path: Path,
    output_path: Optional[Path] = None,
) -> AccountsWorkaroundResult:
    """Temporary workaround to remap default accounts using a user-project mapping."""

    resolved_dataset_path = _resolve_jobs_dataset_path(dataset_path)
    records = _load_jobs_dataset(resolved_dataset_path)
    mapping = _load_user_project_map(mapping_path)
    target_path = output_path or resolved_dataset_path
    remapped_users: set[str] = set()
    rows_updated = 0

    for record in records:
        user_name = record.get("user_name")
        if not user_name:
            continue
        mapped_account = mapping.get(user_name)
        if not mapped_account:
            continue
        current_account = record.get("account")
        if current_account and str(current_account).lower() != "default":
            continue
        record["account"] = mapped_account
        remapped_users.add(user_name)
        rows_updated += 1

    storage_format, resolved_output_path = _write_jobs_dataset(records, target_path)
    return AccountsWorkaroundResult(
        dataset_path=resolved_dataset_path,
        output_path=resolved_output_path,
        rows_scanned=len(records),
        rows_updated=rows_updated,
        users_remapped=sorted(remapped_users),
        storage_format=storage_format,
    )
