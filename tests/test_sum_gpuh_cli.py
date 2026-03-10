from pathlib import Path

import slurm_plot.cli as plot_cli


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_sum_gpuh_sums_gpu_hours(tmp_path: Path) -> None:
    gpuh_file = tmp_path / "gpuhours.csv"
    _write(
        gpuh_file,
        "\n".join(
            [
                "year,account,gpu_hours",
                "2025,aw002,1964.2",
                "2025,b2101,0.2",
                "2025,bx121,0.0",
            ]
        ),
    )

    assert plot_cli._sum_gpuh(str(gpuh_file)) == 1964.4


def test_sum_gpuh_requires_gpu_hours_column(tmp_path: Path) -> None:
    gpuh_file = tmp_path / "gpuhours.csv"
    _write(
        gpuh_file,
        "\n".join(
            [
                "year,account",
                "2025,aw002",
            ]
        ),
    )

    try:
        plot_cli._sum_gpuh(str(gpuh_file))
    except SystemExit as exc:
        assert str(exc) == "GPU hour CSV data missing required columns: gpu_hours"
    else:
        raise AssertionError("Expected SystemExit when gpu_hours column is missing.")
