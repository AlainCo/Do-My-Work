import json
from pathlib import Path

from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverDocumentsTaskSpec,
    RunRequest,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
)
from do_my_work.infrastructure.json_workflow_store import JsonRunRepository, JsonTaskRepository


def test_json_task_repository_saves_and_loads_task_record(tmp_path: Path) -> None:
    repository = JsonTaskRepository(tmp_path / "tasks")
    record = TaskRecord(
        task_key="task:copy:111a",
        spec=CopyFileTaskSpec(
            relative_path=Path("nested/note.md"),
            source_digest="sha256:abcd",
        ),
        status=TaskStatus.SUCCEEDED,
        outcome=TaskOutcome(message="File copied."),
    )

    repository.save(record)
    loaded_record = repository.get("task:copy:111a")

    assert loaded_record == record


def test_json_task_repository_lists_all_records_in_sorted_file_order(tmp_path: Path) -> None:
    repository = JsonTaskRepository(tmp_path / "tasks")
    discover_record = TaskRecord(
        task_key="task:discover:bbb",
        spec=DiscoverDocumentsTaskSpec(root=Path(".")),
        status=TaskStatus.WAITING,
        child_task_keys=["task:copy:aaa"],
        outcome=TaskOutcome(
            message="1 documents discovered",
            created_task_keys=["task:copy:aaa"],
        ),
    )
    copy_record = TaskRecord(
        task_key="task:copy:aaa",
        spec=CopyFileTaskSpec(
            relative_path=Path("alpha.md"),
            source_digest="sha256:aaa",
        ),
        status=TaskStatus.PENDING,
    )

    repository.save(discover_record)
    repository.save(copy_record)

    loaded_records = repository.list_all()

    assert [record.task_key for record in loaded_records] == [
        "task:copy:aaa",
        "task:discover:bbb",
    ]


def test_json_task_repository_returns_none_for_missing_task(tmp_path: Path) -> None:
    repository = JsonTaskRepository(tmp_path / "tasks")

    assert repository.get("task:copy:missing") is None


def test_json_run_repository_saves_run_request_as_json_file(tmp_path: Path) -> None:
    repository = JsonRunRepository(tmp_path / "runs")
    run_request = RunRequest(
        run_id="20260528T210000Z",
        root=Path("docs"),
        status="succeeded",
        root_task_key="task:discover:8f2d",
    )

    repository.save(run_request)

    persisted_files = sorted((tmp_path / "runs").glob("*.json"))
    assert len(persisted_files) == 1
    assert persisted_files[0].name == "20260528T210000Z.json"

    persisted_payload = json.loads(persisted_files[0].read_text(encoding="utf-8"))
    restored_run = RunRequest.model_validate(persisted_payload)

    assert restored_run == run_request