import json
from argparse import Namespace
from datetime import date
from pathlib import Path

import slurm_cli.simple_cli as simple_cli


def test_handle_export_sacct_returns_summary(monkeypatch, tmp_path: Path):
    expected_file = tmp_path / "2024-01-01.csv"

    def fake_export_sacct(*, date_range, output_dir, debug, missing):
        assert date_range.start == date(2024, 1, 1)
        assert date_range.end == date(2024, 1, 31)
        assert output_dir == tmp_path
        assert debug is False
        assert missing is False
        return [expected_file]

    monkeypatch.setattr(simple_cli, "export_sacct", fake_export_sacct)

    args = Namespace(
        date="2024-01",
        start=None,
        end=None,
        output_dir=tmp_path,
        debug=False,
        missing=False,
        reference_date=date(2024, 2, 1),
        command="export-sacct",
    )

    payload = json.loads(simple_cli.handle_export_sacct(args))

    assert payload["output_dir"] == str(tmp_path)
    assert payload["files"] == [str(expected_file)]
    assert payload["days_exported"] == 1
