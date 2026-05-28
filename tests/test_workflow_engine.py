import json
from pathlib import Path

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