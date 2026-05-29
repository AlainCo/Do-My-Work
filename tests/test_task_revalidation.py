from pathlib import Path

from do_my_work.application.task_revalidation import TaskRevalidator
from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverDocumentsTaskSpec,
    MergeFragmentResultsTaskSpec,
    ProcessFragmentTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    WorkspaceConfig,
)


def test_revalidator_marks_succeeded_copy_task_pending_when_output_is_missing(
    tmp_path: Path,
) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    record = TaskRecord(
        task_key="task:copy:abc",
        spec=CopyFileTaskSpec(
            relative_path=Path("alpha.md"),
            source_digest="sha256:abc",
        ),
        status=TaskStatus.SUCCEEDED,
        outcome=TaskOutcome(message="File copied."),
    )

    refreshed_record = TaskRevalidator().revalidate_all([record], config)[0]

    assert refreshed_record.status == TaskStatus.PENDING
    assert refreshed_record.outcome is not None
    assert refreshed_record.outcome.message == "Output file is missing; task must run again."


def test_revalidator_marks_succeeded_discovery_task_waiting_when_child_is_pending() -> None:
    discover_record = TaskRecord(
        task_key="task:discover:abc",
        spec=DiscoverDocumentsTaskSpec(root=Path(".")),
        status=TaskStatus.SUCCEEDED,
        child_task_keys=["task:copy:abc"],
        outcome=TaskOutcome(
            message="1 documents discovered and copied.",
            created_task_keys=["task:copy:abc"],
        ),
    )
    child_record = TaskRecord(
        task_key="task:copy:abc",
        spec=CopyFileTaskSpec(
            relative_path=Path("alpha.md"),
            source_digest="sha256:abc",
        ),
        status=TaskStatus.PENDING,
    )

    refreshed_records = TaskRevalidator().revalidate_all(
        [discover_record, child_record],
        WorkspaceConfig(),
    )

    refreshed_discover_record = next(
        record for record in refreshed_records if record.spec.kind == "discover_documents"
    )
    assert refreshed_discover_record.status == TaskStatus.WAITING
    assert refreshed_discover_record.outcome is not None
    assert refreshed_discover_record.outcome.message == "1 documents discovered."
    assert refreshed_discover_record.outcome.created_task_keys == ["task:copy:abc"]


def test_revalidator_marks_succeeded_merge_task_waiting_when_fragment_child_is_pending(
) -> None:
    merge_record = TaskRecord(
        task_key="task:merge_fragment_results:abc",
        spec=MergeFragmentResultsTaskSpec(
            document_relative_path=Path("note.md"),
            source_digest="sha256:doc",
            fragment_task_keys=["task:process_fragment:abc"],
        ),
        status=TaskStatus.SUCCEEDED,
        outcome=TaskOutcome(message="Fragment length report written."),
    )
    child_record = TaskRecord(
        task_key="task:process_fragment:abc",
        spec=ProcessFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Alpha beta.",
            fragment_digest="sha256:frag",
        ),
        status=TaskStatus.PENDING,
    )

    refreshed_records = TaskRevalidator().revalidate_all(
        [merge_record, child_record],
        WorkspaceConfig(),
    )

    refreshed_merge_record = next(
        record for record in refreshed_records if record.spec.kind == "merge_fragment_results"
    )
    assert refreshed_merge_record.status == TaskStatus.WAITING
    assert refreshed_merge_record.outcome is not None
    assert refreshed_merge_record.outcome.message == "Waiting for fragment results."