from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

import do_my_work.application.task_handlers as task_handlers_module
from do_my_work.application.task_handlers import CheckReferenceUrlTaskHandler
from do_my_work.cli import app
from do_my_work.domain.models import RunRequest, WorkflowRunSummary
from do_my_work.infrastructure.json_workflow_store import JsonRunRepository

runner = CliRunner()


def test_cli_help_only_exposes_workflow_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "compare-runs" in result.stdout
    assert "clean-tasks" in result.stdout
    assert "copy-resource-tree" in result.stdout
    assert "reference-index-tree" in result.stdout
    assert "spurious-file-report" in result.stdout
    assert "translate-document-tree" in result.stdout
    assert "hello" not in result.stdout
    assert "copy-tree" not in result.stdout
    assert "summary-document-tree" not in result.stdout


def test_translate_document_tree_help_mentions_with_review_option() -> None:
    result = runner.invoke(app, ["translate-document-tree", "--help"])

    assert result.exit_code == 0
    assert "--with-review" in result.stdout


def test_translate_document_tree_command_reports_missing_config_file_cleanly(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing-workspace.yaml"

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(missing_config),
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 2
    assert f"Error: Config file not found: {missing_config}" in output
    assert "Traceback" not in output


def test_translate_document_tree_command_reports_invalid_config_cleanly(tmp_path: Path) -> None:
    config_file = tmp_path / "workspace.yaml"
    config_file.write_text(
        (
            "llm:\n"
            "  translator:\n"
            "    technical:\n"
            "      url: http://mock.example:11434\n"
            "      model: ollama-mock\n"
            "      temperature: 0.0\n"
            "      system_prompt: You are a translator.\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 2
    assert f"Error: Invalid configuration in {config_file}:" in output
    assert "llm.translator.technical.user_prompt: Field required" in output
    assert "Traceback" not in output


def test_translate_document_tree_command_reports_unknown_translator_profile_cleanly(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text("# Intro\n", encoding="utf-8")
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
            "      system_prompt: You are a translator.\n"
            "      user_prompt: ${input_fragment}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
            "--translator-profile",
            "missing-profile",
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 2
    assert "Invalid value for --translator-profile: Unknown translator profile:" in output
    assert "missing-profile" in output
    assert "Traceback" not in output


def test_translate_document_tree_command_reports_missing_input_root_cleanly(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    input_dir.mkdir(parents=True)
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
            "      system_prompt: You are a translator.\n"
            "      user_prompt: ${input_fragment}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
            "--root",
            "missing-subtree",
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 2
    assert f"Error: Input root does not exist: {input_dir / 'missing-subtree'}" in output
    assert "Traceback" not in output


def test_spurious_file_report_command_reports_missing_input_root_cleanly(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    input_dir.mkdir(parents=True)
    config_file.write_text(
        (
            f"input_dir: {input_dir.as_posix()}\n"
            f"output_dir: {output_dir.as_posix()}\n"
            f"data_dir: {data_dir.as_posix()}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "spurious-file-report",
            "--config",
            str(config_file),
            "--root",
            "missing-subtree",
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 2
    assert f"Error: Input root does not exist: {input_dir / 'missing-subtree'}" in output
    assert "Traceback" not in output


def test_translate_document_tree_command_reports_invalid_local_workflow_config_cleanly(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    (input_dir / "docs").mkdir(parents=True)
    (input_dir / "docs" / "note.md").write_text("# Intro\n", encoding="utf-8")
    (input_dir / "docs" / "do-my-work.yaml").write_text(
        "version: 1\n"
        "translation:\n"
        "  rules:\n"
        "    - match: \"*.md\"\n"
        "      hints: 123\n",
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
            "      system_prompt: You are a translator.\n"
            "      user_prompt: ${input_fragment}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 2
    assert f"Error: Invalid configuration in {input_dir / 'docs' / 'do-my-work.yaml'}:" in output
    assert "translation.rules.0.hints: Input should be a valid string" in output
    assert "Traceback" not in output


def test_translate_document_tree_command_reports_invalid_local_workflow_yaml_cleanly(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    (input_dir / "docs").mkdir(parents=True)
    (input_dir / "docs" / "note.md").write_text("# Intro\n", encoding="utf-8")
    (input_dir / "docs" / "do-my-work.yaml").write_text(
        "version: 1\n"
        "translation:\n"
        "  rules:\n"
        "    - match: \"README.md\"\n"
        "      profile: technical\n"
        "      translated_document_header:|\n"
        "        # Broken block scalar\n",
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
            "      system_prompt: You are a translator.\n"
            "      user_prompt: ${input_fragment}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 2
    assert f"Error: Invalid YAML in {input_dir / 'docs' / 'do-my-work.yaml'} at line 7, column 9:" in output
    assert "could not find expected ':'" in output
    assert "Traceback" not in output


def test_translate_document_tree_command_exits_nonzero_when_local_profile_override_is_missing(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    (input_dir / "docs").mkdir(parents=True)
    (input_dir / "docs" / "note.md").write_text("# Intro\n", encoding="utf-8")
    (input_dir / "docs" / "do-my-work.yaml").write_text(
        "version: 1\n"
        "translation:\n"
        "  rules:\n"
        "    - match: \"*.md\"\n"
        "      profile: missing-profile\n",
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
            "      system_prompt: You are a translator.\n"
            "      user_prompt: ${input_fragment}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 1
    assert "Workflow run completed:" in output
    assert "failed=1" in output
    assert "Error: Translator profile does not exist." in output
    assert "missing-profile for docs/note.md" in output
    assert "Traceback" not in output


def test_clean_tasks_command_removes_persisted_task_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    task_dir = data_dir / "tasks" / "translate_fragment"
    task_dir.mkdir(parents=True)
    (task_dir / "task__translate_fragment__frag-001.json").write_text(
        "{}",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "clean-tasks",
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0
    assert f"Data directory: {data_dir}" in result.stdout
    assert "Task files removed: 1" in result.stdout
    assert not (data_dir / "tasks").exists()


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
    assert "Active task states: pending=0 waiting=0 succeeded=4 failed=0" in result.stdout
    assert "LLM call timings: attempts=0 avg_seconds=0.000 std_dev_seconds=0.000" in result.stdout
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
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/alice\n\n"
        "References:\n"
        "- nested/other.md [Further Reading] Alice\n\n"
        "### https://example.org/bob\n\n"
        "References:\n"
        "- note.md [Sources] Bob\n"
    )


def test_reference_index_tree_command_writes_reports_in_input_when_requested(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
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
            "--report-to-input",
        ],
    )

    assert result.exit_code == 0
    assert f"Output directory: {input_dir}" in result.stdout
    assert (input_dir / "note.references.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Index\n\n"
        "Source: note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )
    assert (input_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/bob\n\n"
        "References:\n"
        "- note.md [Sources] Bob\n"
    )
    assert not (output_dir / "note.references.md").exists()
    assert not (output_dir / "references.index.md").exists()


def test_reference_index_tree_command_checks_urls_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/files/report.pdf).\n",
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/pdf",
                "content-disposition": 'attachment; filename="report.pdf"',
            },
            request=request,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(CheckReferenceUrlTaskHandler, "_get_http_client", lambda self: http_client)
    monkeypatch.setattr(CheckReferenceUrlTaskHandler, "close", lambda self: None)
    monkeypatch.setattr(
        task_handlers_module,
        "_build_checked_at_timestamp",
        lambda: "2026-05-31T10:00:00Z",
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
            "--check-urls",
        ],
    )

    assert result.exit_code == 0
    assert "Tasks executed: 4" in result.stdout
    assert "Tasks created: 3" in result.stdout
    assert (output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## note.md\n\n"
        "- [Bob](https://example.org/files/report.pdf) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/files/report.pdf\n\n"
        "- Status: 200 OK\n"
        "- Last checked: 2026-05-31T10:00:00Z\n"
        "- Content-Type: application/pdf\n"
        "- Filename: report.pdf\n\n"
        "References:\n"
        "- note.md [Sources] Bob\n"
    )


def test_reference_index_tree_command_excludes_relative_links_from_url_cross_reference(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Sources\n\nSee [Local](./appendix.md).\n\nSee [Bob](https://example.org/bob).\n",
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
    assert (output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## note.md\n\n"
        "- [Local](./appendix.md) [Sources]\n"
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/bob\n\n"
        "References:\n"
        "- note.md [Sources] Bob\n"
    )


def test_copy_resource_tree_command_copies_selected_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    (input_dir / "assets").mkdir(parents=True)
    (input_dir / "assets" / "logo.jpeg").write_bytes(b"jpeg-bytes")
    (input_dir / "assets" / "notes.txt").write_text("skip", encoding="utf-8")
    config_file.write_text(
        (
            f"input_dir: {input_dir.as_posix()}\n"
            f"output_dir: {output_dir.as_posix()}\n"
            f"data_dir: {data_dir.as_posix()}\n"
            "resource_selection:\n"
            "  default_action: exclude\n"
            "  rules:\n"
            "    - match: assets/**/*.jpeg\n"
            "      action: include\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "copy-resource-tree",
            "--config",
            str(config_file),
        ],
    )

    assert result.exit_code == 0
    assert "Workflow run completed:" in result.stdout
    assert "Tasks executed: 2" in result.stdout
    assert "Failed tasks retried: 0" in result.stdout
    assert "Tasks created: 1" in result.stdout
    assert "Active task states: pending=0 waiting=0 succeeded=2 failed=0" in result.stdout
    assert (output_dir / "assets" / "logo.jpeg").read_bytes() == b"jpeg-bytes"
    assert not (output_dir / "assets" / "notes.txt").exists()


def test_spurious_file_report_command_writes_markdown_report(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = output_dir / "work" / "data"
    config_file = tmp_path / "workspace.yaml"

    (input_dir / "docs").mkdir(parents=True)
    (input_dir / "docs" / "note.md").write_text("# Intro\n", encoding="utf-8")
    (input_dir / "docs" / "do-my-work.yaml").write_text(
        "version: 1\n"
        "spurious:\n"
        "  rules:\n"
        "    - match: \"manual/**/*\"\n"
        "      exclude: true\n",
        encoding="utf-8",
    )
    (input_dir / "assets").mkdir(parents=True)
    (input_dir / "assets" / "logo.jpeg").write_bytes(b"jpeg-bytes")

    (output_dir / "docs").mkdir(parents=True)
    (output_dir / "docs" / "note.md").write_text("translated", encoding="utf-8")
    (output_dir / "docs" / "old.md").write_text("stale", encoding="utf-8")
    (output_dir / "docs" / "note.references.md").write_text("ignore", encoding="utf-8")
    (output_dir / "docs" / "manual").mkdir(parents=True)
    (output_dir / "docs" / "manual" / "keep.md").write_text("manual", encoding="utf-8")
    (output_dir / "assets").mkdir(parents=True)
    (output_dir / "assets" / "logo.jpeg").write_bytes(b"jpeg-bytes")
    (output_dir / "manual").mkdir(parents=True)
    (output_dir / "manual" / "outside.txt").write_text("ignore", encoding="utf-8")
    data_dir.mkdir(parents=True)
    (data_dir / "task.json").write_text("{}", encoding="utf-8")

    config_file.write_text(
        (
            f"input_dir: {input_dir.as_posix()}\n"
            f"output_dir: {output_dir.as_posix()}\n"
            f"data_dir: {data_dir.as_posix()}\n"
            "resource_selection:\n"
            "  default_action: exclude\n"
            "  rules:\n"
            "    - match: assets/**/*.jpeg\n"
            "      action: include\n"
            "spurious_detection:\n"
            "  default_action: include\n"
            "  rules:\n"
            "    - match: manual/**/*\n"
            "      action: exclude\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "spurious-file-report",
            "--config",
            str(config_file),
        ],
    )

    assert result.exit_code == 0
    assert f"Report path: {output_dir / 'spurious-files.md'}" in result.stdout
    assert "Checked output files: 3" in result.stdout
    assert "Ignored output files: 4" in result.stdout
    assert "Spurious output files: 1" in result.stdout
    assert "Missing output files: 0" in result.stdout
    assert (output_dir / "spurious-files.md").read_text(encoding="utf-8") == (
        "# Spurious Output File Report\n\n"
        "Root: .\n\n"
        "- Expected translated documents: 1\n"
        "- Expected copied resources: 1\n"
        "- Checked output files: 3\n"
        "- Ignored output files: 4\n"
        "- Spurious output files: 1\n"
        "- Spurious translated documents: 1\n"
        "- Spurious copied resources: 0\n"
        "- Other spurious output files: 0\n"
        "- Missing output files: 0\n"
        "- Missing translated documents: 0\n"
        "- Missing copied resources: 0\n\n"
        "## Spurious Files\n\n"
        "### Spurious Translated Documents\n\n"
        "- docs/old.md\n\n"
        "## Missing Files\n\n"
        "None.\n"
    )


def test_spurious_file_report_command_writes_report_in_input_when_requested(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = output_dir / "work" / "data"
    config_file = tmp_path / "workspace.yaml"

    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text("# Intro\n", encoding="utf-8")
    (output_dir / "note.md").write_text("translated", encoding="utf-8")
    data_dir.mkdir(parents=True)

    config_file.write_text(
        (
            f"input_dir: {input_dir.as_posix()}\n"
            f"output_dir: {output_dir.as_posix()}\n"
            f"data_dir: {data_dir.as_posix()}\n"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "spurious-file-report",
            "--config",
            str(config_file),
            "--report-to-input",
        ],
    )

    assert result.exit_code == 0
    assert f"Report path: {input_dir / 'spurious-files.md'}" in result.stdout
    assert "Spurious output files: 0" in result.stdout
    assert "Missing output files: 0" in result.stdout
    assert (input_dir / "spurious-files.md").exists()
    assert not (output_dir / "spurious-files.md").exists()


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
            "        ${input_fragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    from do_my_work.infrastructure.llm_client import OllamaLlmClient

    monkeypatch.setattr(
        OllamaLlmClient,
        "translate_fragment",
        lambda self, config, profile_name, parameters: (
            self._record_attempt_duration(1.0),
            str(parameters["input_fragment"]).upper(),
        )[1],
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
    assert "Active task states: pending=0 waiting=0 succeeded=5 failed=0" in result.stdout
    assert "LLM call timings: attempts=2 avg_seconds=1.000 std_dev_seconds=0.000" in result.stdout
    assert (output_dir / "note.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n"
    )


def test_translate_document_tree_command_writes_review_html_when_requested(
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
            "translation_review:\n"
            "  translated_first: true\n"
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
            "        ${input_fragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    from do_my_work.infrastructure.llm_client import OllamaLlmClient

    monkeypatch.setattr(
        OllamaLlmClient,
        "translate_fragment",
        lambda self, config, profile_name, parameters: (
            self._record_attempt_duration(1.0),
            str(parameters["input_fragment"]).upper(),
        )[1],
    )

    result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
            "--with-review",
        ],
    )

    assert result.exit_code == 0
    review_html = (output_dir / "note.review.html").read_text(encoding="utf-8")
    assert "Translation Review" in review_html
    assert review_html.index(">Translated<") < review_html.index(">Original<")
    assert "<h1>INTRO</h1>" in review_html
    assert "<h1>Intro</h1>" in review_html


def test_translate_document_tree_command_adds_review_on_later_run_without_retranslation(
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
            "translation_review:\n"
            "  translated_first: true\n"
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
            "        ${input_fragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    from do_my_work.infrastructure.llm_client import OllamaLlmClient

    translation_call_count = 0

    def fake_translate_fragment(self, config, profile_name, parameters):
        nonlocal translation_call_count
        translation_call_count += 1
        self._record_attempt_duration(1.0)
        return str(parameters["input_fragment"]).upper()

    monkeypatch.setattr(
        OllamaLlmClient,
        "translate_fragment",
        fake_translate_fragment,
    )

    first_result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    assert first_result.exit_code == 0
    assert translation_call_count == 2
    assert (output_dir / "note.md").exists()
    assert not (output_dir / "note.review.html").exists()

    second_result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
            "--with-review",
        ],
    )

    assert second_result.exit_code == 0
    assert translation_call_count == 2
    assert (output_dir / "note.review.html").exists()
    assert "Tasks replayed:" in second_result.stdout
    review_html = (output_dir / "note.review.html").read_text(encoding="utf-8")
    assert "Translation Review" in review_html
    assert review_html.index(">Translated<") < review_html.index(">Original<")


def test_translate_document_tree_command_reorders_review_columns_without_retranslation(
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
            "translation_review:\n"
            "  translated_first: false\n"
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
            "        ${input_fragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    from do_my_work.infrastructure.llm_client import OllamaLlmClient

    translation_call_count = 0

    def fake_translate_fragment(self, config, profile_name, parameters):
        nonlocal translation_call_count
        translation_call_count += 1
        self._record_attempt_duration(1.0)
        return str(parameters["input_fragment"]).upper()

    monkeypatch.setattr(
        OllamaLlmClient,
        "translate_fragment",
        fake_translate_fragment,
    )

    first_result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
            "--with-review",
        ],
    )

    assert first_result.exit_code == 0
    assert translation_call_count == 2
    first_review_html = (output_dir / "note.review.html").read_text(encoding="utf-8")
    assert first_review_html.index(">Original<") < first_review_html.index(">Translated<")

    config_file.write_text(
        (
            f"input_dir: {input_dir.as_posix()}\n"
            f"output_dir: {output_dir.as_posix()}\n"
            f"data_dir: {data_dir.as_posix()}\n"
            "translation_review:\n"
            "  translated_first: true\n"
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
            "        ${input_fragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    second_result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
            "--with-review",
        ],
    )

    assert second_result.exit_code == 0
    assert translation_call_count == 2
    second_review_html = (output_dir / "note.review.html").read_text(encoding="utf-8")
    assert second_review_html.index(">Translated<") < second_review_html.index(">Original<")


def test_translate_document_tree_command_rerenders_local_header_footer_without_retranslation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    config_file = tmp_path / "workspace.yaml"

    input_dir.mkdir(parents=True)
    (input_dir / "README.md").write_text(
        "# Intro\n\nAlpha beta.\n",
        encoding="utf-8",
    )
    (input_dir / "do-my-work.yaml").write_text(
        "version: 1\n"
        "translation:\n"
        "  rules:\n"
        "    - match: \"README.md\"\n"
        "      translated_document_header: \"<!-- First header -->\"\n"
        "      translated_document_footer: \"<!-- First footer -->\"\n",
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
            "        ${input_fragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    from do_my_work.infrastructure.llm_client import OllamaLlmClient

    translation_call_count = 0

    def fake_translate_fragment(self, config, profile_name, parameters):
        nonlocal translation_call_count
        translation_call_count += 1
        self._record_attempt_duration(1.0)
        return str(parameters["input_fragment"]).upper()

    monkeypatch.setattr(
        OllamaLlmClient,
        "translate_fragment",
        fake_translate_fragment,
    )

    first_result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    assert first_result.exit_code == 0
    first_translation_call_count = translation_call_count
    assert first_translation_call_count == 2
    assert (output_dir / "README.md").read_text(encoding="utf-8") == (
        "<!-- First header -->\n\n"
        "# INTRO\n\n"
        "ALPHA BETA.\n\n"
        "<!-- First footer -->\n"
    )

    (input_dir / "do-my-work.yaml").write_text(
        "version: 1\n"
        "translation:\n"
        "  rules:\n"
        "    - match: \"README.md\"\n"
        "      translated_document_header: \"<!-- Second header -->\"\n"
        "      translated_document_footer: \"<!-- Second footer -->\"\n",
        encoding="utf-8",
    )

    second_result = runner.invoke(
        app,
        [
            "translate-document-tree",
            "--config",
            str(config_file),
        ],
    )

    assert second_result.exit_code == 0
    assert translation_call_count == first_translation_call_count
    assert "Tasks replayed:" in second_result.stdout
    assert (output_dir / "README.md").read_text(encoding="utf-8") == (
        "<!-- Second header -->\n\n"
        "# INTRO\n\n"
        "ALPHA BETA.\n\n"
        "<!-- Second footer -->\n"
    )


def test_compare_runs_command_compares_latest_two_runs(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    repository = JsonRunRepository(data_dir / "runs")
    repository.save(
        RunRequest(
            run_id="20260530T200000Z",
            request_kind="translate_document_tree",
            root=Path("docs"),
            status="succeeded",
            root_task_key="task:discover_translate_documents:older",
            summary=WorkflowRunSummary(
                executed_task_count=5,
                created_task_count=4,
                succeeded_task_count=5,
                llm_call_attempt_count=2,
                llm_call_average_seconds=1.2,
                llm_call_variance_seconds=0.04,
            ),
        )
    )
    repository.save(
        RunRequest(
            run_id="20260530T201000Z",
            request_kind="translate_document_tree",
            root=Path("docs"),
            status="succeeded",
            root_task_key="task:discover_translate_documents:newer",
            summary=WorkflowRunSummary(
                executed_task_count=7,
                created_task_count=6,
                succeeded_task_count=7,
                llm_call_attempt_count=3,
                llm_call_average_seconds=0.8,
                llm_call_variance_seconds=0.01,
            ),
        )
    )

    result = runner.invoke(
        app,
        [
            "compare-runs",
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0
    assert f"Data directory: {data_dir}" in result.stdout
    assert "Comparing runs: 20260530T200000Z -> 20260530T201000Z" in result.stdout
    assert "Request kind: translate_document_tree -> translate_document_tree" in result.stdout
    assert "- Tasks executed: 7 (+2)" in result.stdout
    assert "- Tasks created: 6 (+2)" in result.stdout
    assert "- LLM call attempts: 3 (+1)" in result.stdout
    assert "- LLM avg seconds: 0.800 (-0.400)" in result.stdout


def test_compare_runs_command_defaults_to_previous_run_of_same_request_kind(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    repository = JsonRunRepository(data_dir / "runs")
    repository.save(
        RunRequest(
            run_id="20260530T200000Z",
            request_kind="translate_document_tree",
            root=Path("docs"),
            status="succeeded",
            root_task_key="task:discover_translate_documents:older-translate",
            summary=WorkflowRunSummary(executed_task_count=5, succeeded_task_count=5),
        )
    )
    repository.save(
        RunRequest(
            run_id="20260530T200500Z",
            request_kind="reference_index_tree",
            root=Path("docs"),
            status="succeeded",
            root_task_key="task:discover_reference_documents:middle-reference",
            summary=WorkflowRunSummary(executed_task_count=4, succeeded_task_count=4),
        )
    )
    repository.save(
        RunRequest(
            run_id="20260530T201000Z",
            request_kind="translate_document_tree",
            root=Path("docs"),
            status="succeeded",
            root_task_key="task:discover_translate_documents:newer-translate",
            summary=WorkflowRunSummary(executed_task_count=7, succeeded_task_count=7),
        )
    )

    result = runner.invoke(
        app,
        [
            "compare-runs",
            "--data-dir",
            str(data_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Comparing runs: 20260530T200000Z -> 20260530T201000Z" in result.stdout
    assert "Request kind: translate_document_tree -> translate_document_tree" in result.stdout


def test_compare_runs_command_rejects_explicit_mixed_request_kinds(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    repository = JsonRunRepository(data_dir / "runs")
    repository.save(
        RunRequest(
            run_id="20260530T200000Z",
            request_kind="translate_document_tree",
            root=Path("docs"),
            status="succeeded",
            root_task_key="task:discover_translate_documents:older",
            summary=WorkflowRunSummary(executed_task_count=5, succeeded_task_count=5),
        )
    )
    repository.save(
        RunRequest(
            run_id="20260530T201000Z",
            request_kind="reference_index_tree",
            root=Path("docs"),
            status="succeeded",
            root_task_key="task:discover_reference_documents:newer",
            summary=WorkflowRunSummary(executed_task_count=4, succeeded_task_count=4),
        )
    )

    result = runner.invoke(
        app,
        [
            "compare-runs",
            "--data-dir",
            str(data_dir),
            "--older-run-id",
            "20260530T200000Z",
            "--newer-run-id",
            "20260530T201000Z",
        ],
    )

    assert result.exit_code != 0
    assert "Selected runs have different request kinds" in (result.stdout + result.stderr)