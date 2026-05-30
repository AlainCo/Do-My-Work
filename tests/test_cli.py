from pathlib import Path

import pytest
from typer.testing import CliRunner

from do_my_work.cli import app
from do_my_work.domain.models import RunRequest, WorkflowRunSummary
from do_my_work.infrastructure.json_workflow_store import JsonRunRepository

runner = CliRunner()


def test_cli_help_only_exposes_reference_and_translation_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "compare-runs" in result.stdout
    assert "clean-tasks" in result.stdout
    assert "reference-index-tree" in result.stdout
    assert "translate-document-tree" in result.stdout
    assert "hello" not in result.stdout
    assert "copy-tree" not in result.stdout
    assert "summary-document-tree" not in result.stdout


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
    assert "LLM call timings: attempts=0 avg_seconds=0.000 variance_seconds=0.000" in result.stdout
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
            "        ${input_fragment}\n"
            "        ===END SOURCE TEXT===\n"
        ),
        encoding="utf-8",
    )

    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    monkeypatch.setattr(
        OllamaChatClient,
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
    assert "LLM call timings: attempts=2 avg_seconds=1.000 variance_seconds=0.000" in result.stdout
    assert (output_dir / "note.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n"
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