import csv
from argparse import Namespace
from pathlib import Path

import slurm_plot.cli as plot_cli


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _read_csv(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def test_handle_project_information_combines_sources(tmp_path: Path) -> None:
    pi_path = tmp_path / "project-pi-map.txt"
    gpu_path = tmp_path / "project-gpuhours-map.txt"
    dss_path = tmp_path / "project-dss-map.txt"
    output_path = tmp_path / "output.csv"

    _write_text(
        pi_path,
        "\n".join(
            [
                "pn25da Univ.Prof.Dr. Stefan Feuerriegel (ra52med)",
                "pn25ju Univ.Prof. Frauke Kreuter (lu26cix)",
            ]
        ),
    )
    _write_text(
        gpu_path,
        "\n".join(
            [
                "year,account,gpu_hours",
                "2025,pn25da,10",
                "2025,pn25da,2.5",
                "2025,pn25ju,7.75",
            ]
        ),
    )
    _write_text(
        dss_path,
        "\n".join(
            [
                "Project,Quota GB,Assigned GB,Used GB",
                "pn25da,4500,4500,3824",
                "pn25ju,6500,6500,6018",
            ]
        ),
    )

    args = Namespace(
        input_pi=str(pi_path),
        input_gpuh=str(gpu_path),
        input_dss=str(dss_path),
        output=str(output_path),
    )

    assert plot_cli.handle_project_information(args) == str(output_path)

    rows = _read_csv(output_path)
    assert rows[0] == ["ProjectID", "PI", "GPU hours", "DSS Assigned", "DSS Used"]
    assert rows[1][0] == "pn25da"
    assert rows[1][2] == "12.5"
    assert rows[1][3:] == ["4500", "3824"]
    assert rows[2][0] == "pn25ju"
    assert rows[2][2] == "7.75"
    assert rows[2][3:] == ["6500", "6018"]


def test_handle_project_information_requires_at_least_one_input(tmp_path: Path) -> None:
    args = Namespace(
        input_pi=None,
        input_gpuh=None,
        input_dss=None,
        output=str(tmp_path / "output.csv"),
    )

    try:
        plot_cli.handle_project_information(args)
    except SystemExit as exc:
        assert str(exc) == "Provide at least one input file."
    else:
        raise AssertionError("Expected SystemExit when no inputs are provided.")
