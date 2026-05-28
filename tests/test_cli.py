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


def test_copy_tree_command_copies_markdown_documents_and_persists_state(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    (input_dir / "nested").mkdir(parents=True)
    (input_dir / "nested" / "note.md").write_text("hello\n", encoding="utf-8")
    (input_dir / "nested" / "ignored.txt").write_text("ignore\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "copy-tree",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0
    stdout_lines = result.stdout.splitlines()
    assert stdout_lines[0] == f"Input directory: {input_dir}"
    assert stdout_lines[1] == f"Output directory: {output_dir}"
    assert stdout_lines[2] == f"Data directory: {data_dir}"
    assert "Workflow run completed:" in result.stdout
    assert "Tasks executed: 2" in result.stdout
    assert "Tasks replayed: 0" in result.stdout
    assert "Tasks created: 1" in result.stdout
    assert "Tasks unchanged: 0" in result.stdout
    assert (output_dir / "nested" / "note.md").read_text(encoding="utf-8") == "hello\n"
    assert not (output_dir / "nested" / "ignored.txt").exists()
    assert len(list((data_dir / "runs").glob("*.json"))) == 1
    assert len(list((data_dir / "tasks").glob("*.json"))) == 2