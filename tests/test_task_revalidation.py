from pathlib import Path

from do_my_work.application.task_revalidation import TaskRevalidator
from do_my_work.domain.models import (
    DiscoverTranslateDocumentsTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    TranslateFragmentTaskSpec,
    WorkspaceConfig,
)


def test_revalidator_leaves_translate_fragment_record_unchanged() -> None:
    record = TaskRecord(
        task_key="task:translate_fragment:abc",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Alpha beta.",
            fragment_digest="sha256:frag",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.SUCCEEDED,
        outcome=TaskOutcome(message="Fragment translated."),
    )

    refreshed_record = TaskRevalidator().revalidate_all([record], WorkspaceConfig())[0]

    assert refreshed_record == record


def test_revalidator_marks_translate_discovery_waiting_when_child_is_pending() -> None:
    discover_record = TaskRecord(
        task_key="task:discover_translate_documents:abc",
        spec=DiscoverTranslateDocumentsTaskSpec(
            root=Path("."),
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.SUCCEEDED,
        child_task_keys=["task:discover_translate_document_fragments:abc"],
        outcome=TaskOutcome(
            message="1 documents discovered and translated.",
            created_task_keys=["task:discover_translate_document_fragments:abc"],
        ),
    )
    child_record = TaskRecord(
        task_key="task:discover_translate_document_fragments:abc",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Alpha beta.",
            fragment_digest="sha256:frag",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.PENDING,
    )

    refreshed_records = TaskRevalidator().revalidate_all(
        [discover_record, child_record],
        WorkspaceConfig(),
    )

    refreshed_discover_record = next(
        record
        for record in refreshed_records
        if record.spec.kind == "discover_translate_documents"
    )
    assert refreshed_discover_record.status == TaskStatus.WAITING
    assert refreshed_discover_record.outcome is not None
    assert refreshed_discover_record.outcome.message == "1 documents discovered."
    assert refreshed_discover_record.outcome.created_task_keys == [
        "task:discover_translate_document_fragments:abc"
    ]