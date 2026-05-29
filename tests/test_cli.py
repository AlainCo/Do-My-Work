from pathlib import Path

import pytest
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


def test_summary_document_tree_command_generates_markdown_report(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n\n- Item one\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "summary-document-tree",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Workflow run completed:" in result.stdout
    assert "Tasks executed: 6" in result.stdout
    assert "Tasks created: 5" in result.stdout

    report_path = output_dir / "note.summary.md"
    assert report_path.read_text(encoding="utf-8") == (
        "# Fragment Length Report\n\n"
        "Source: note.md\n\n"
        "- heading [Intro] -> 5\n"
        "- paragraph [Intro] -> 11\n"
        "- list_item [Intro] -> 8\n"
    )
    assert len(list((data_dir / "runs").glob("*.json"))) == 1
    assert len(list((data_dir / "tasks").glob("*.json"))) == 6


def test_translate_document_tree_command_translates_markdown_fragments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n",
        encoding="utf-8",
    )
    config_file.write_text(
        (
            f"input_dir: {input_dir.as_posix()}\n"
            f"output_dir: {output_dir.as_posix()}\n"
            f"data_dir: {data_dir.as_posix()}\n"
            "llm:\n"
            "  translator:\n"
            "    technical:\n"
            "      url: http://mock.example:11434\n"
            "      model: ollama-mock\n"
            "      temperature: 0.0\n"
            "      system_prompt: |\n"
            "        You are a professional translatoir from french to english.\n"
            "      user_prompt: |\n"
            "        ===BEGIN SOURCE TEXT===\n"
            "        ${inputfragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        lambda self, config, profile_name, parameters: str(parameters["inputfragment"]).upper(),
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Workflow run completed:" in result.stdout
    assert "Tasks executed: 5" in result.stdout
    assert (output_dir / "note.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n"
    )