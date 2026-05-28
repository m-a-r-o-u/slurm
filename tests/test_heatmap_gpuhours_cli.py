from pathlib import Path
from unittest.mock import patch

import slurm_plot.cli as plot_cli


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_gpu_hours_heatmap_sorts_rows_and_quarters_and_fills_gaps() -> None:
    data = plot_cli._load_gpu_hours_heatmap(
        "\n".join(
            [
                "3months,account,gpu_hours",
                "2025-04..2025-06,b2101,5000",
                "2025-01..2025-03,bx121,10",
                "2025-01..2025-03,b2101,0.2",
                "2025-04..2025-06,ax999,12000",
            ]
        )
    )

    assert data.entity_label == "project"
    assert list(data.column_labels) == ["2025 Q1", "2025 Q2"]
    assert list(data.row_labels) == ["ax999", "b2101", "bx121"]
    assert data.values == [
        [0.0, 12000.0],
        [0.2, 5000.0],
        [10.0, 0.0],
    ]


def test_load_gpu_hours_heatmap_accepts_user_input() -> None:
    data = plot_cli._load_gpu_hours_heatmap(
        "\n".join(
            [
                "quarter,user,gpu_hours",
                "2025-07..2025-09,apdl011,466.6",
                "2025-01..2025-03,apdl006,143.2",
            ]
        )
    )

    assert data.entity_label == "user"
    assert list(data.column_labels) == ["2025 Q1", "2025 Q3"]
    assert list(data.row_labels) == ["apdl011", "apdl006"]
    assert data.values == [[0.0, 466.6], [143.2, 0.0]]


def test_handle_heatmap_gpuhours_writes_requested_output(tmp_path: Path) -> None:
    input_path = tmp_path / "gpuh.csv"
    output_path = tmp_path / "nested" / "heatmap-gpuh.pdf"
    _write(
        input_path,
        "\n".join(
            [
                "3months,account,gpu_hours",
                "2025-01..2025-03,b2101,0.2",
            ]
        ),
    )
    args = plot_cli._build_parser().parse_args(
        [
            "heatmap-gpuhours",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    with patch("slurm_plot.cli.plot_gpu_hours_heatmap") as plot_heatmap:
        result = plot_cli.handle_heatmap_gpuhours(args)

    assert result == str(output_path)
    assert output_path.parent.is_dir()
    plot_heatmap.assert_called_once()
    called_data = plot_heatmap.call_args.args[0]
    assert list(called_data.row_labels) == ["b2101"]
    assert list(called_data.column_labels) == ["2025 Q1"]
    assert plot_heatmap.call_args.kwargs["output_path"] == str(output_path)
