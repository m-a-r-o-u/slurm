"""Metrics pipeline for transforming sacct exports into analytics datasets."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional


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


def _write_jobs_dataset(records: list[dict], output_path: Path) -> str:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(records)
        pq.write_table(table, output_path)
        return "parquet"
    except Exception:
        # Fallback to JSON when pyarrow is unavailable
        output_path.write_text(json.dumps(records, default=str, indent=2))
        return "json"


def build_metrics(*, input_dir: Path, output_path: Path) -> MetricsBuildResult:
    csv_files = sorted(input_dir.glob("*.csv"))
    raw_records = _load_sacct_exports(csv_files)
    jobs = _derive_jobs(raw_records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    storage_format = _write_jobs_dataset(jobs, output_path)

    return MetricsBuildResult(
        source_files=csv_files,
        output_path=output_path,
        rows_written=len(jobs),
        storage_format=storage_format,
    )
