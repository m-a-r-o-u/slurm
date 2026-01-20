from datetime import date
from pathlib import Path
import json

import pytest

from slurm_cli.dates import DateRange
from slurm_cli.metrics import build_metrics, format_query_result, query_metrics
import slurm_cli.simple_cli as simple_cli


CSV_SAMPLE = """JobIDRaw,User,Account,Partition,Submit,Start,End,State,ExitCode,ElapsedRaw,AllocTRES
5362466,di35qir2,default,mcml-hgx-h100-94x4,2025-10-26T16:20:17,2025-10-30T20:12:14,2025-11-01T20:12:40,TIMEOUT,0:0,172826,"billing=614560,cpu=40,gres/gpu=4,mem=300G,node=1"
7000000,ab12cd,default,lrz,2025-01-01T00:00:00,,,COMPLETED,0:0,3600,"billing=10,cpu=2,mem=2G,node=1"
"""


def test_build_metrics_writes_dataset(tmp_path: Path):
    csv_path = tmp_path / "sacct-exports"
    csv_path.mkdir()
    source_file = csv_path / "2025-10-26.csv"
    source_file.write_text(CSV_SAMPLE)

    output_path = tmp_path / "metrics" / "jobs_data.parquet"

    result = build_metrics(input_dir=csv_path, output_path=output_path)

    if result.storage_format == "json":
        expected_output_path = output_path.with_suffix(".json")
    else:
        expected_output_path = output_path
    assert result.output_path == expected_output_path
    assert result.source_files == [source_file]
    assert result.rows_written == 2
    assert expected_output_path.exists()
    assert result.storage_format in {"parquet", "json"}

    raw_payload = expected_output_path.read_text()
    records = json.loads(raw_payload)
    rows = {row["job_id"]: row for row in records}

    first = rows[5362466]
    assert first["gpu_count"] == 4
    assert first["cpu_count"] == 40
    assert first["mem_req_mb"] == 307200
    assert round(first["gpu_hours"], 3) == round(172826 / 3600 * 4, 3)
    assert first["wait_s"] == 359517
    assert first["date_key"] == "2025-11-01"
    assert first["is_failed"] is True
    assert first["is_wasted"] is True
    assert str(first["__source_file"]).endswith("2025-10-26.csv")

    second = rows[7000000]
    assert second["gpu_count"] == 0
    assert second["start_ts"] is None
    assert second["end_ts"] is None
    assert second["wait_s"] is None
    assert second["date_key"] == "2025-01-01"
    assert second["is_gpu_job"] is False
    assert second["is_failed"] is False
    assert second["is_wasted"] is False


def test_simple_cli_metrics_build_runs(monkeypatch, tmp_path: Path):
    output_path = tmp_path / "jobs_data.parquet"

    from slurm_cli import metrics as metrics_module

    def fake_build_metrics(*, input_dir, output_path):
        assert input_dir == tmp_path
        return metrics_module.build_metrics(input_dir=input_dir, output_path=output_path)

    csv_file = tmp_path / "2024-01-01.csv"
    csv_file.write_text(CSV_SAMPLE)

    args = simple_cli.argparse.Namespace(
        command="metrics",
        metrics_command="build",
        input_dir=tmp_path,
        output_path=output_path,
    )

    monkeypatch.setattr(simple_cli, "build_metrics", fake_build_metrics)

    payload = json.loads(simple_cli.handle_metrics_build(args))
    if payload["storage_format"] == "json":
        expected_path = str(output_path.with_suffix(".json"))
    else:
        expected_path = str(output_path)

    assert payload["output_path"] == expected_path
    assert payload["source_files"] == [str(csv_file)]


def test_simple_cli_metrics_query_runs(tmp_path: Path):
    dataset_path = tmp_path / "jobs_data.parquet"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "job_id": 1,
                    "end_ts": "2025-03-01T00:00:00+00:00",
                    "account": "demo",
                    "gpu_hours": 12.0,
                }
            ]
        )
    )

    args = simple_cli.argparse.Namespace(
        command="metrics",
        metrics_command="query",
        metric="gpu_hours",
        dataset_path=dataset_path,
        by="account",
        stat=None,
        start=None,
        end=None,
        date=None,
        format="json",
    )

    payload = json.loads(simple_cli.handle_metrics_query(args))

    assert payload["metric"] == "gpu_hours"
    assert payload["stat"] == "sum"
    assert payload["rows"] == [{"account": "demo", "gpu_hours": 12.0}]


def test_simple_cli_metrics_query_with_select(tmp_path: Path):
    dataset_path = tmp_path / "jobs_data.parquet"
    dataset_path.write_text(
        json.dumps(
            [
                {"end_ts": "2025-03-01T00:00:00+00:00", "user_name": "keep", "gpu_hours": 2},
                {"end_ts": "2025-03-01T00:00:00+00:00", "user_name": "skip", "gpu_hours": 5},
            ]
        )
    )

    args = simple_cli.argparse.Namespace(
        command="metrics",
        metrics_command="query",
        metric="gpu_hours",
        dataset_path=dataset_path,
        by="",
        stat=None,
        start=None,
        end=None,
        date=None,
        format="json",
        select=["user:keep"],
    )

    payload = json.loads(simple_cli.handle_metrics_query(args))
    assert payload["rows"] == [{"gpu_hours": 2.0}]


def test_query_metrics_groups_and_stats(tmp_path: Path):
    dataset_path = tmp_path / "jobs_data.parquet"
    records = [
        {
            "job_id": 1,
            "end_ts": "2025-01-15T00:00:00+00:00",
            "account": "a",
            "partition": "p1",
            "user_name": "u1",
            "state": "COMPLETED",
            "gpu_hours": 10.0,
        },
        {
            "job_id": 2,
            "end_ts": "2025-01-20T00:00:00+00:00",
            "account": "a",
            "partition": "p1",
            "user_name": "u1",
            "state": "COMPLETED",
            "gpu_hours": 6.0,
        },
        {
            "job_id": 3,
            "end_ts": "2025-02-01T00:00:00+00:00",
            "account": "b",
            "partition": "p2",
            "user_name": "u2",
            "state": "FAILED",
            "gpu_hours": 4.0,
        },
    ]
    dataset_path.write_text(json.dumps(records))

    result = query_metrics("gpu_hours", dataset_path=dataset_path, by=["month", "account"])
    assert result.stat == "sum"
    assert result.by == ["month", "account"]
    assert result.rows == [
        {"month": "2025-01", "account": "a", "gpu_hours": 16.0},
        {"month": "2025-02", "account": "b", "gpu_hours": 4.0},
    ]

    mean_result = query_metrics("gpu_hours", dataset_path=dataset_path, by=["account"], stat="mean")
    assert mean_result.stat == "mean"
    assert mean_result.rows == [
        {"account": "a", "gpu_hours": 8.0},
        {"account": "b", "gpu_hours": 4.0},
    ]

    with pytest.raises(ValueError):
        query_metrics("gpu_hours", dataset_path=dataset_path, by=["account", "month"])


def test_query_metrics_date_filter_and_table_format(tmp_path: Path):
    dataset_path = tmp_path / "jobs_data.parquet"
    records = [
        {
            "job_id": 1,
            "end_ts": "2025-03-01T00:00:00+00:00",
            "account": "demo",
            "user_name": "u1",
            "gpu_hours": 10.0,
        },
        {
            "job_id": 2,
            "end_ts": "2025-03-05T00:00:00+00:00",
            "account": "demo",
            "user_name": "u2",
            "gpu_hours": 5.0,
        },
        {
            "job_id": 3,
            "end_ts": "2025-04-01T00:00:00+00:00",
            "account": "demo",
            "user_name": "u3",
            "gpu_hours": 20.0,
        },
    ]
    dataset_path.write_text(json.dumps(records))

    date_range = DateRange(start=date(2025, 3, 1), end=date(2025, 3, 31))
    result = query_metrics(
        "gpu_hours",
        dataset_path=dataset_path,
        by=["user"],
        date_range=date_range,
    )

    assert len(result.rows) == 2
    assert {row["user"] for row in result.rows} == {"u1", "u2"}

    table = format_query_result(result, output_format="table")
    assert "user | gpu_hours" in table
    assert "u1" in table and "u2" in table


def test_query_metrics_csv_format(tmp_path: Path):
    dataset_path = tmp_path / "jobs_data.parquet"
    records = [
        {
            "job_id": 1,
            "end_ts": "2025-03-01T00:00:00+00:00",
            "month": "2025-03",
            "user_name": "u1",
            "gpu_hours": 10.0,
        },
        {
            "job_id": 2,
            "end_ts": "2025-03-02T00:00:00+00:00",
            "month": "2025-03",
            "user_name": "u2",
            "gpu_hours": 5.0,
        },
    ]
    dataset_path.write_text(json.dumps(records))

    result = query_metrics(
        "gpu_hours",
        dataset_path=dataset_path,
        by=["month", "user"],
    )

    csv_output = format_query_result(result, output_format="csv")
    lines = csv_output.splitlines()
    assert lines[0] == "month,user,gpu_hours"
    assert "2025-03,u1,10.0" in lines
    assert "2025-03,u2,5.0" in lines


def test_query_metrics_select_filters(tmp_path: Path):
    dataset_path = tmp_path / "jobs_data.parquet"
    records = [
        {
            "job_id": 1,
            "end_ts": "2025-03-01T00:00:00+00:00",
            "partition": "mcml-hgx-h100-94x4",
            "account": "team-a",
            "user_name": "u1",
            "state": "COMPLETED",
            "gpu_hours": 10.0,
        },
        {
            "job_id": 2,
            "end_ts": "2025-03-02T00:00:00+00:00",
            "partition": "mcml-something",
            "account": "team-b",
            "user_name": "u2",
            "state": "FAILED",
            "gpu_hours": 5.0,
        },
        {
            "job_id": 3,
            "end_ts": "2025-03-03T00:00:00+00:00",
            "partition": "other", 
            "account": "team-b",
            "user_name": "u1",
            "state": "FAILED",
            "gpu_hours": 8.0,
        },
    ]
    dataset_path.write_text(json.dumps(records))

    result = query_metrics(
        "gpu_hours",
        dataset_path=dataset_path,
        selectors=["partition:mcml*;user:u1"],
    )

    assert result.rows == [{"gpu_hours": 10.0}]

    second = query_metrics(
        "gpu_hours",
        dataset_path=dataset_path,
        selectors=["partition:mcml*", "account:team-b"],
    )

    assert result.stat == "sum"
    assert second.rows == [{"gpu_hours": 5.0}]

    with pytest.raises(ValueError):
        query_metrics(
            "gpu_hours",
            dataset_path=dataset_path,
            selectors=["unknown:*"]
        )
