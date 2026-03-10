from pathlib import Path

import slurm_plot.cli as plot_cli


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_combine_gpuh_info_merges_rows_and_headers(tmp_path: Path) -> None:
    mcml = tmp_path / "mcml.csv"
    lrz = tmp_path / "lrz.csv"
    _write(
        mcml,
        "\n".join(
            [
                "year,account,gpu_hours",
                "2025,pn25ke,8018.8",
                "2025,pn25ju,16410.5",
            ]
        ),
    )
    _write(
        lrz,
        "\n".join(
            [
                "year,account,gpu_hours",
                "2025,pn25ju,1436.6",
                "2025,b2101,0.2",
            ]
        ),
    )

    out = plot_cli._combine_gpuh_info(
        [str(mcml), str(lrz)],
        ["MCML", "LRZ"],
        project_list_path=None,
        institution=None,
    )

    lines = out.splitlines()
    assert lines[0] == "year,ProjectID,Partner,MCML,LRZ"
    assert "2025,b2101,,,0.2" in lines
    assert "2025,pn25ju,,16410.5,1436.6" in lines
    assert "2025,pn25ke,,8018.8," in lines


def test_combine_gpuh_info_filters_institution_and_keeps_partner(tmp_path: Path) -> None:
    mcml = tmp_path / "mcml.csv"
    lrz = tmp_path / "lrz.csv"
    projects = tmp_path / "project-list.csv"

    _write(
        mcml,
        "\n".join(
            [
                "year,account,gpu_hours",
                "2025,pn25ke,8018.8",
                "2025,pn25ju,16410.5",
            ]
        ),
    )
    _write(
        lrz,
        "\n".join(
            [
                "year,account,gpu_hours",
                "2025,pn25ju,1436.6",
                "2025,b2101,0.2",
            ]
        ),
    )
    _write(
        projects,
        "\n".join(
            [
                "ProjectID,Partner,Institution",
                "pn25ke,mcml,Technische Universität München",
                "pn25ju,,Technische Universität München",
                "b2101,,FAU Erlangen-Nürnberg",
            ]
        ),
    )

    out = plot_cli._combine_gpuh_info(
        [str(mcml), str(lrz)],
        ["MCML", "LRZ"],
        project_list_path=str(projects),
        institution="Technische Universität München",
    )

    lines = out.splitlines()
    assert lines[0] == "year,ProjectID,Partner,MCML,LRZ"
    assert "2025,pn25ke,mcml,8018.8," in lines
    assert "2025,pn25ju,,16410.5,1436.6" in lines
    assert all("b2101" not in line for line in lines)
