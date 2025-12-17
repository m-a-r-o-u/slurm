from datetime import date
from types import SimpleNamespace

from slurm_cli.dates import DateRange
from slurm_cli.exports import SACCT_FIELDS, _sacct_command, export_sacct


def _runner_factory(outputs, commands):
    def _runner(command, **_kwargs):
        commands.append(command)
        stdout = outputs[len(commands) - 1]
        return SimpleNamespace(stdout=stdout)

    return _runner


def test_sacct_export_writes_daily_files(tmp_path):
    date_range = DateRange(start=date(2025, 12, 1), end=date(2025, 12, 2))
    outputs = [
        "1|alice|acct|gpu|2025-12-01T00:30:00|2025-12-01T01:00:00|2025-12-01T02:00:00|F|0:0|3600|gres/gpu=1",
        "",
    ]
    commands: list[str] = []
    runner = _runner_factory(outputs, commands)

    generated = export_sacct(date_range=date_range, output_dir=tmp_path, runner=runner)

    assert commands == [
        _sacct_command(date(2025, 12, 1), date(2025, 12, 2)),
        _sacct_command(date(2025, 12, 2), date(2025, 12, 3)),
    ]
    assert len(generated) == 2

    first_file = generated[0]
    assert first_file.name == "2025-12-01.csv"
    content = first_file.read_text().strip().splitlines()
    assert content[0].split(",") == SACCT_FIELDS
    assert content[1].split(",") == outputs[0].split("|")

    second_file = generated[1]
    assert second_file.read_text().strip().splitlines() == [",".join(SACCT_FIELDS)]
