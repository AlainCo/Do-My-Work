from pathlib import Path

import pytest
from pydantic import ValidationError

from do_my_work.domain.models import (
    DiscoverReferenceDocumentsTaskSpec,
    DiscoverTranslateDocumentsTaskSpec,
    MergeReferenceIndexesTaskSpec,
    RunRequest,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    TranslatedFragmentResult,
    TranslateFragmentTaskSpec,
)


def test_run_request_uses_reference_index_defaults() -> None:
    run_request = RunRequest(run_id="run-001", root_task_key="task:discover:001")

    assert run_request.request_kind == "reference_index_tree"
    assert run_request.root == Path(".")
    assert run_request.status == "pending"


def test_task_record_round_trips_translated_fragment_result() -> None:
    original_record = TaskRecord(
        task_key="task:translate_fragment:111a",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("docs/sample.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Alpha beta.",
            pre_context="# Intro",
            post_context="Next paragraph.",
            fragment_digest="sha256:frag",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.SUCCEEDED,
        outcome=TaskOutcome(
            message="Fragment translated.",
            result=TranslatedFragmentResult(
                translated_text="ALPHA BETA.",
                length=11,
            ),
        ),
    )

    persisted_payload = original_record.model_dump(mode="json")
    restored_record = TaskRecord.model_validate(persisted_payload)

    assert isinstance(restored_record.spec, TranslateFragmentTaskSpec)
    assert restored_record.outcome is not None
    assert restored_record.spec.pre_context == "# Intro"
    assert restored_record.spec.post_context == "Next paragraph."
    assert restored_record.outcome.result == TranslatedFragmentResult(
        translated_text="ALPHA BETA.",
        length=11,
    )


def test_task_record_rejects_legacy_copy_spec_json_shape() -> None:
    with pytest.raises(ValidationError):
        TaskRecord.model_validate(
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


def test_task_record_round_trips_translate_root_task_as_json_data() -> None:
    original_record = TaskRecord(
        task_key="task:discover_translate_documents:111a",
        spec=DiscoverTranslateDocumentsTaskSpec(
            root=Path("."),
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.WAITING,
        child_task_keys=["task:discover_translate_document_fragments:222b"],
        outcome=TaskOutcome(
            message="1 documents discovered.",
            created_task_keys=["task:discover_translate_document_fragments:222b"],
        ),
    )

    restored_record = TaskRecord.model_validate(original_record.model_dump(mode="json"))

    assert isinstance(restored_record.spec, DiscoverTranslateDocumentsTaskSpec)
    assert restored_record.spec.profile_name == "technical"
    assert restored_record.spec.profile_digest == "sha256:profile"


def test_task_record_round_trips_reference_root_task_as_json_data() -> None:
    original_record = TaskRecord(
        task_key="task:discover_reference_documents:111a",
        spec=DiscoverReferenceDocumentsTaskSpec(root=Path(".")),
        status=TaskStatus.WAITING,
        child_task_keys=["task:index_markdown_references:222b"],
        outcome=TaskOutcome(
            message="1 documents discovered.",
            created_task_keys=["task:index_markdown_references:222b"],
        ),
    )

    restored_record = TaskRecord.model_validate(original_record.model_dump(mode="json"))

    assert isinstance(restored_record.spec, DiscoverReferenceDocumentsTaskSpec)
    assert restored_record.child_task_keys == ["task:index_markdown_references:222b"]


def test_task_record_round_trips_reference_merge_task_as_json_data() -> None:
    original_record = TaskRecord(
        task_key="task:merge_reference_indexes:111a",
        spec=MergeReferenceIndexesTaskSpec(
            root=Path("."),
            document_relative_paths=[Path("alpha.md"), Path("nested/beta.md")],
            reference_task_keys=[
                "task:index_markdown_references:222b",
                "task:index_markdown_references:333c",
            ],
        ),
        status=TaskStatus.WAITING,
        child_task_keys=[
            "task:index_markdown_references:222b",
            "task:index_markdown_references:333c",
        ],
        outcome=TaskOutcome(message="Waiting for reference index results."),
    )

    restored_record = TaskRecord.model_validate(original_record.model_dump(mode="json"))

    assert isinstance(restored_record.spec, MergeReferenceIndexesTaskSpec)
    assert restored_record.spec.document_relative_paths == [
        Path("alpha.md"),
        Path("nested/beta.md"),
    ]