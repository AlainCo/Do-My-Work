import json
from pathlib import Path

from do_my_work.domain.models import (
    DiscoverTranslateDocumentFragmentsTaskSpec,
    RunRequest,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    TranslateFragmentTaskSpec,
    WorkflowRunSummary,
)
from do_my_work.infrastructure.json_workflow_store import JsonRunRepository, JsonTaskRepository


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
        summary=WorkflowRunSummary(
            executed_task_count=4,
            created_task_count=3,
            succeeded_task_count=4,
        ),
    )

    repository.save(run_request)

    persisted_files = sorted((tmp_path / "runs").glob("*.json"))
    assert len(persisted_files) == 1
    assert persisted_files[0].name == "20260528T210000Z.json"

    persisted_payload = json.loads(persisted_files[0].read_text(encoding="utf-8"))
    restored_run = RunRequest.model_validate(persisted_payload)

    assert restored_run == run_request


def test_json_run_repository_gets_and_lists_saved_runs(tmp_path: Path) -> None:
    repository = JsonRunRepository(tmp_path / "runs")
    older_run = RunRequest(
        run_id="20260528T210000Z",
        root_task_key="task:discover:older",
    )
    newer_run = RunRequest(
        run_id="20260528T220000Z",
        root_task_key="task:discover:newer",
    )

    repository.save(newer_run)
    repository.save(older_run)

    assert repository.get(older_run.run_id) == older_run
    assert repository.list_all() == [older_run, newer_run]


def test_json_task_repository_stores_task_in_kind_subdirectory(tmp_path: Path) -> None:
    repository = JsonTaskRepository(tmp_path / "tasks")
    record = TaskRecord(
        task_key="task:translate_fragment:frag-001",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Alpha beta.",
            pre_context="",
            post_context="",
            fragment_digest="sha256:frag",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.SUCCEEDED,
        outcome=TaskOutcome(message="done"),
    )

    repository.save(record)

    persisted_file = (
        tmp_path
        / "tasks"
        / "translate_fragment"
        / "task__translate_fragment__frag-001.json"
    )
    assert persisted_file.exists()
    assert repository.get(record.task_key) == record


def test_json_task_repository_reads_legacy_flat_task_file(tmp_path: Path) -> None:
    repository = JsonTaskRepository(tmp_path / "tasks")
    record = TaskRecord(
        task_key="task:discover_translate_document_fragments:doc-001",
        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
            relative_path=Path("note.md"),
            source_digest="sha256:doc",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.PENDING,
    )

    legacy_file = tmp_path / "tasks" / "task__discover_translate_document_fragments__doc-001.json"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    assert repository.get(record.task_key) == record
    assert repository.list_all() == [record]