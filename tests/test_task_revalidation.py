from pathlib import Path

from do_my_work.application.task_revalidation import TaskRevalidator
from do_my_work.domain.models import (
    DiscoverTranslateDocumentFragmentsTaskSpec,
    DiscoverTranslateDocumentsTaskSpec,
    MergeTranslatedFragmentsTaskSpec,
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


def test_revalidator_marks_failed_translate_fragment_pending_for_retry() -> None:
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
        status=TaskStatus.FAILED,
        outcome=TaskOutcome(message="LLM translation timed out.", error="timeout"),
    )

    refreshed_record = TaskRevalidator().revalidate_all([record], WorkspaceConfig())[0]

    assert refreshed_record.status == TaskStatus.PENDING
    assert refreshed_record.outcome is not None
    assert refreshed_record.outcome.message == "Previous failed translation will be retried."


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


def test_revalidator_reopens_failed_translation_parents_when_child_is_retried() -> None:
    root_record = TaskRecord(
        task_key="task:discover_translate_documents:root",
        spec=DiscoverTranslateDocumentsTaskSpec(
            root=Path("."),
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.FAILED,
        child_task_keys=["task:discover_translate_document_fragments:doc"],
        outcome=TaskOutcome(
            message="1 documents discovered, at least one translation task failed.",
            created_task_keys=["task:discover_translate_document_fragments:doc"],
        ),
    )
    discover_record = TaskRecord(
        task_key="task:discover_translate_document_fragments:doc",
        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
            relative_path=Path("note.md"),
            source_digest="sha256:doc",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.FAILED,
        child_task_keys=[
            "task:translate_fragment:frag",
            "task:merge_translated_fragments:doc",
        ],
        outcome=TaskOutcome(
            message="1 fragments discovered, at least one translation task failed.",
            created_task_keys=[
                "task:translate_fragment:frag",
                "task:merge_translated_fragments:doc",
            ],
        ),
    )
    fragment_record = TaskRecord(
        task_key="task:translate_fragment:frag",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Alpha beta.",
            fragment_digest="sha256:frag",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.FAILED,
        outcome=TaskOutcome(message="LLM translation timed out.", error="timeout"),
    )
    merge_record = TaskRecord(
        task_key="task:merge_translated_fragments:doc",
        spec=MergeTranslatedFragmentsTaskSpec(
            document_relative_path=Path("note.md"),
            source_digest="sha256:doc",
            fragment_task_keys=["task:translate_fragment:frag"],
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.FAILED,
        child_task_keys=["task:translate_fragment:frag"],
        outcome=TaskOutcome(message="At least one fragment task failed."),
    )

    refreshed_records = TaskRevalidator().revalidate_all(
        [root_record, discover_record, fragment_record, merge_record],
        WorkspaceConfig(),
    )
    refreshed_index = {record.task_key: record for record in refreshed_records}

    assert refreshed_index["task:translate_fragment:frag"].status == TaskStatus.PENDING
    assert refreshed_index["task:merge_translated_fragments:doc"].status == TaskStatus.WAITING
    assert refreshed_index["task:discover_translate_document_fragments:doc"].status == (
        TaskStatus.WAITING
    )
    assert refreshed_index["task:discover_translate_documents:root"].status == TaskStatus.WAITING