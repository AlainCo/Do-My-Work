import json
from pathlib import Path

import pytest

from do_my_work.application.workflow_engine import WorkflowEngine
from do_my_work.domain.models import RunRequest, TaskRecord, WorkspaceConfig


def test_workflow_engine_copies_tree_and_persists_run_state(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    (input_dir / "nested").mkdir(parents=True)
    (input_dir / "alpha.md").write_text("alpha\n", encoding="utf-8")
    (input_dir / "nested" / "beta.md").write_text("beta\n", encoding="utf-8")

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    run_request = WorkflowEngine().run(config, root=Path("."))

    assert run_request.status == "succeeded"
    assert (output_dir / "alpha.md").read_text(encoding="utf-8") == "alpha\n"
    assert (output_dir / "nested" / "beta.md").read_text(encoding="utf-8") == "beta\n"

    persisted_run_files = sorted((data_dir / "runs").glob("*.json"))
    assert len(persisted_run_files) == 1
    persisted_run = RunRequest.model_validate_json(
        persisted_run_files[0].read_text(encoding="utf-8")
    )
    assert persisted_run.run_id == run_request.run_id
    assert persisted_run.status == "succeeded"

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").glob("*.json"))
    ]

    assert len(persisted_tasks) == 3

    discover_task = next(
        task for task in persisted_tasks if task.spec.kind == "discover_documents"
    )
    copy_tasks = [task for task in persisted_tasks if task.spec.kind == "copy_file"]

    assert discover_task.status.value == "succeeded"
    assert len(discover_task.child_task_keys) == 2
    assert all(task.status.value == "succeeded" for task in copy_tasks)
    assert sorted(task.spec.relative_path for task in copy_tasks) == [
        Path("alpha.md"),
        Path("nested/beta.md"),
    ]


def test_workflow_engine_discovers_only_markdown_documents(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    (input_dir / "nested").mkdir(parents=True)
    (input_dir / "alpha.md").write_text("alpha\n", encoding="utf-8")
    (input_dir / "notes.txt").write_text("ignore me\n", encoding="utf-8")
    (input_dir / "nested" / "beta.MD").write_text("beta\n", encoding="utf-8")

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    WorkflowEngine().run(config, root=Path("."))

    assert (output_dir / "alpha.md").read_text(encoding="utf-8") == "alpha\n"
    assert (output_dir / "nested" / "beta.MD").read_text(encoding="utf-8") == "beta\n"
    assert not (output_dir / "notes.txt").exists()

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").glob("*.json"))
    ]

    discover_task = next(
        task for task in persisted_tasks if task.spec.kind == "discover_documents"
    )
    copy_tasks = [task for task in persisted_tasks if task.spec.kind == "copy_file"]

    assert len(discover_task.child_task_keys) == 2
    assert sorted(task.spec.relative_path for task in copy_tasks) == [
        Path("alpha.md"),
        Path("nested/beta.MD"),
    ]


def test_workflow_engine_fails_when_requested_root_is_missing(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )

    run_request = WorkflowEngine().run(config, root=Path("missing"))

    assert run_request.status == "failed"

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((config.data_dir / "tasks").glob("*.json"))
    ]

    assert len(persisted_tasks) == 1
    assert persisted_tasks[0].spec.kind == "discover_documents"
    assert persisted_tasks[0].status.value == "failed"
    assert persisted_tasks[0].outcome is not None
    assert persisted_tasks[0].outcome.message == "Input root does not exist."


def test_workflow_engine_recreates_missing_output_from_succeeded_copy_task(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "alpha.md").write_text("alpha\n", encoding="utf-8")

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    first_run = WorkflowEngine().run(config, root=Path("."))
    assert first_run.status == "succeeded"
    assert (output_dir / "alpha.md").exists()

    (output_dir / "alpha.md").unlink()

    second_run = WorkflowEngine().run(config, root=Path("."))

    assert second_run.status == "succeeded"
    assert (output_dir / "alpha.md").read_text(encoding="utf-8") == "alpha\n"

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").glob("*.json"))
    ]

    copy_task = next(task for task in persisted_tasks if task.spec.kind == "copy_file")
    assert copy_task.status.value == "succeeded"
    assert copy_task.outcome is not None
    assert copy_task.outcome.message == "File copied."


def test_workflow_engine_runs_summary_flow_via_fragment_tasks(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n\n- Item one\n",
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
        request_kind="summary_document_tree",
    )

    assert run_request.status == "succeeded"
    assert run_request.summary.executed_task_count == 6
    assert run_request.summary.created_task_count == 5
    assert (output_dir / "note.summary.md").read_text(encoding="utf-8") == (
        "# Fragment Length Report\n\n"
        "Source: note.md\n\n"
        "- heading [Intro] -> 5\n"
        "- paragraph [Intro] -> 11\n"
        "- list_item [Intro] -> 8\n"
    )

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").glob("*.json"))
    ]

    assert len(persisted_tasks) == 6
    assert sorted(task.spec.kind for task in persisted_tasks) == [
        "discover_document_fragments",
        "discover_summary_documents",
        "merge_fragment_results",
        "process_fragment",
        "process_fragment",
        "process_fragment",
    ]


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