from pathlib import Path

from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverFilesTaskSpec,
    RunRequest,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
)


def test_run_request_uses_copy_tree_defaults() -> None:
    run_request = RunRequest(run_id="run-001", root_task_key="task:discover:001")

    assert run_request.request_kind == "copy_tree"
    assert run_request.root == Path(".")
    assert run_request.status == "pending"


def test_task_record_validates_copy_file_spec_from_json_shape() -> None:
    task_record = TaskRecord.model_validate(
        {
            "task_key": "task:copy:111a",
            "spec": {
                "kind": "copy_file",
                "relative_path": "testsubdir/subtest1.md",
                "source_digest": "sha256:abcd",
            },
            "status": "succeeded",
            "outcome": {
                "message": "File copied",
            },
        }
    )

    assert isinstance(task_record.spec, CopyFileTaskSpec)
    assert task_record.spec.relative_path == Path("testsubdir/subtest1.md")
    assert task_record.status == TaskStatus.SUCCEEDED
    assert task_record.outcome == TaskOutcome(message="File copied")


def test_task_record_round_trips_discover_files_record_as_json_data() -> None:
    original_record = TaskRecord(
        task_key="task:discover:8f2d",
        spec=DiscoverFilesTaskSpec(root=Path(".")),
        status=TaskStatus.WAITING,
        child_task_keys=["task:copy:111a", "task:copy:222b"],
        outcome=TaskOutcome(
            message="2 files discovered",
            created_task_keys=["task:copy:111a", "task:copy:222b"],
        ),
    )

    persisted_payload = original_record.model_dump(mode="json")
    restored_record = TaskRecord.model_validate(persisted_payload)

    assert isinstance(restored_record.spec, DiscoverFilesTaskSpec)
    assert restored_record.spec.root == Path(".")
    assert restored_record.status == TaskStatus.WAITING
    assert restored_record.child_task_keys == ["task:copy:111a", "task:copy:222b"]
    assert restored_record.outcome is not None
    assert restored_record.outcome.created_task_keys == ["task:copy:111a", "task:copy:222b"]