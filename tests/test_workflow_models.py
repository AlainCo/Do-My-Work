from pathlib import Path

from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverDocumentsTaskSpec,
    DiscoverReferenceDocumentsTaskSpec,
    DiscoverTranslateDocumentsTaskSpec,
    MergeReferenceIndexesTaskSpec,
    ProcessedFragmentResult,
    ProcessFragmentTaskSpec,
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


def test_task_record_round_trips_discover_documents_record_as_json_data() -> None:
    original_record = TaskRecord(
        task_key="task:discover:8f2d",
        spec=DiscoverDocumentsTaskSpec(root=Path(".")),
        status=TaskStatus.WAITING,
        child_task_keys=["task:copy:111a", "task:copy:222b"],
        outcome=TaskOutcome(
            message="2 documents discovered",
            created_task_keys=["task:copy:111a", "task:copy:222b"],
        ),
    )

    persisted_payload = original_record.model_dump(mode="json")
    restored_record = TaskRecord.model_validate(persisted_payload)

    assert isinstance(restored_record.spec, DiscoverDocumentsTaskSpec)
    assert restored_record.spec.root == Path(".")
    assert restored_record.status == TaskStatus.WAITING
    assert restored_record.child_task_keys == ["task:copy:111a", "task:copy:222b"]
    assert restored_record.outcome is not None
    assert restored_record.outcome.created_task_keys == ["task:copy:111a", "task:copy:222b"]


def test_task_record_round_trips_processed_fragment_result() -> None:
    original_record = TaskRecord(
        task_key="task:process_fragment:111a",
        spec=ProcessFragmentTaskSpec(
            document_relative_path=Path("docs/sample.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Alpha beta.",
            fragment_digest="sha256:frag",
        ),
        status=TaskStatus.SUCCEEDED,
        outcome=TaskOutcome(
            message="Fragment processed.",
            result=ProcessedFragmentResult(
                rendered_text="- paragraph [Intro] -> 11",
                length=11,
            ),
        ),
    )

    persisted_payload = original_record.model_dump(mode="json")
    restored_record = TaskRecord.model_validate(persisted_payload)

    assert isinstance(restored_record.spec, ProcessFragmentTaskSpec)
    assert restored_record.outcome is not None
    assert restored_record.outcome.result == ProcessedFragmentResult(
        rendered_text="- paragraph [Intro] -> 11",
        length=11,
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