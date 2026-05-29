from pathlib import Path

import pytest
from typer.testing import CliRunner

from do_my_work.cli import app

runner = CliRunner()


def test_cli_help_only_exposes_reference_and_translation_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "reference-index-tree" in result.stdout
    assert "translate-document-tree" in result.stdout
    assert "hello" not in result.stdout
    assert "copy-tree" not in result.stdout
    assert "summary-document-tree" not in result.stdout


def test_reference_index_tree_command_generates_markdown_reference_report(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    (input_dir / "nested").mkdir(parents=True)
    (input_dir / "nested" / "other.md").write_text(
        "# Further Reading\n\nSee [Alice](https://example.org/alice).\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "reference-index-tree",
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
    assert "Tasks executed: 4" in result.stdout
    assert "Failed tasks retried: 0" in result.stdout
    assert "Tasks created: 3" in result.stdout
    assert (output_dir / "note.references.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Index\n\n"
        "Source: note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )
    assert (output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## nested/other.md\n\n"
        "- [Alice](https://example.org/alice) [Further Reading]\n\n"
        "## note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )


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
    assert "Failed tasks retried: 0" in result.stdout
    assert (output_dir / "note.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n"
    )