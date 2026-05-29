import json
from pathlib import Path

import httpx
import pytest

from do_my_work.application.workflow_engine import WorkflowEngine
from do_my_work.domain.models import TaskRecord, WorkspaceConfig


def test_workflow_engine_runs_reference_index_flow(tmp_path: Path) -> None:
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

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    run_request = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="reference_index_tree",
    )

    assert run_request.status == "succeeded"
    assert run_request.summary.executed_task_count == 4
    assert run_request.summary.retried_failed_task_count == 0
    assert run_request.summary.created_task_count == 3
    assert (output_dir / "note.references.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Index\n\n"
        "Source: note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )
    assert (output_dir / "nested" / "other.references.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Index\n\n"
        "Source: nested/other.md\n\n"
        "- [Alice](https://example.org/alice) [Further Reading]\n"
    )
    assert (output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## nested/other.md\n\n"
        "- [Alice](https://example.org/alice) [Further Reading]\n\n"
        "## note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").glob("*.json"))
    ]
    assert len(persisted_tasks) == 4
    assert sorted(task.spec.kind for task in persisted_tasks) == [
        "discover_reference_documents",
        "index_markdown_references",
        "index_markdown_references",
        "merge_reference_indexes",
    ]


def test_workflow_engine_runs_translation_flow_via_fragment_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n\n- Item one\n",
        encoding="utf-8",
    )

    from do_my_work.domain.models import LlmConfig, TranslatorProfileConfig
    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        lambda self, config, profile_name, parameters: str(parameters["inputfragment"]).upper(),
    )

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    temperature=0.0,
                    system_prompt="You are a professional translatoir from french to english.",
                    user_prompt=(
                        "===BEGIN SOURCE TEXT===\n"
                        "${inputfragment}\n"
                        "===END SOURCE TEXT===\n"
                    ),
                )
            }
        ),
    )

    run_request = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert run_request.status == "succeeded"
    assert run_request.summary.executed_task_count == 6
    assert run_request.summary.retried_failed_task_count == 0
    assert run_request.summary.created_task_count == 5
    assert (output_dir / "note.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n\n- ITEM ONE\n"
    )

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").glob("*.json"))
    ]
    assert len(persisted_tasks) == 6
    assert sorted(task.spec.kind for task in persisted_tasks) == [
        "discover_translate_document_fragments",
        "discover_translate_documents",
        "merge_translated_fragments",
        "translate_fragment",
        "translate_fragment",
        "translate_fragment",
    ]


def test_workflow_engine_retries_failed_translation_tasks_on_next_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n",
        encoding="utf-8",
    )

    from do_my_work.domain.models import LlmConfig, TranslatorProfileConfig
    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    call_count = {"value": 0}

    def flaky_translate_fragment(self, config, profile_name, parameters):
        del self, config, profile_name
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise httpx.ReadTimeout("temporary timeout")
        return str(parameters["inputfragment"]).upper()

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        flaky_translate_fragment,
    )

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    temperature=0.0,
                    system_prompt="You are a professional translatoir from french to english.",
                    user_prompt=(
                        "===BEGIN SOURCE TEXT===\n"
                        "${inputfragment}\n"
                        "===END SOURCE TEXT===\n"
                    ),
                )
            }
        ),
    )

    first_run = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert first_run.status == "failed"
    assert first_run.summary.retried_failed_task_count == 0

    second_run = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert second_run.status == "succeeded"
    assert second_run.summary.retried_failed_task_count == 1
    assert (output_dir / "note.md").read_text(encoding="utf-8") == "# INTRO\n\nALPHA BETA.\n"