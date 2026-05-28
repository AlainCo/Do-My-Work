from pathlib import Path

from typer.testing import CliRunner

from do_my_work.cli import app

runner = CliRunner()


def test_hello_command_without_config_uses_defaults() -> None:
    result = runner.invoke(app, ["hello"])

    assert result.exit_code == 0
    assert "Workspace configuration loaded." in result.stdout
    assert "Input directory: work\\input" in result.stdout
    assert "Output directory: work\\output" in result.stdout
    assert "Data directory: work\\data" in result.stdout


def test_hello_command_with_yaml_config(tmp_path: Path) -> None:
    config_file = tmp_path / "workspace.yaml"
    config_file.write_text(
        "input_dir: inbound\noutput_dir: outbound\ndata_dir: state\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "hello",
            "--config",
            str(config_file),
            "--output-dir",
            "published",
        ],
    )

    assert result.exit_code == 0
    assert "Input directory: inbound" in result.stdout
    assert "Output directory: published" in result.stdout
    assert "Data directory: state" in result.stdout