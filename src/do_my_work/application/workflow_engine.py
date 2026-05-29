import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from do_my_work.application.task_handlers import (
    DiscoverReferenceDocumentsTaskHandler,
    DiscoverTranslateDocumentFragmentsTaskHandler,
    DiscoverTranslateDocumentsTaskHandler,
    IndexMarkdownReferencesTaskHandler,
    MergeReferenceIndexesTaskHandler,
    MergeTranslatedFragmentsTaskHandler,
    TranslateFragmentTaskHandler,
)
from do_my_work.application.task_keys import (
    make_discover_reference_documents_task_key,
    make_discover_translate_documents_task_key,
    make_translator_profile_digest,
)
from do_my_work.application.task_revalidation import TaskRevalidator
from do_my_work.domain.models import (
    DiscoverReferenceDocumentsTaskSpec,
    DiscoverTranslateDocumentsTaskSpec,
    RunRequest,
    TaskRecord,
    TaskStatus,
    WorkflowRunResult,
    WorkflowRunSummary,
    WorkspaceConfig,
)
from do_my_work.infrastructure.json_workflow_store import JsonRunRepository, JsonTaskRepository


class WorkflowEngine:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def run(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
        request_kind: Literal[
            "reference_index_tree",
            "translate_document_tree",
        ] = "reference_index_tree",
        translator_profile: str = "technical",
    ) -> WorkflowRunResult:
        task_repository = JsonTaskRepository(config.data_dir / "tasks")
        run_repository = JsonRunRepository(config.data_dir / "runs")
        executed_task_keys: set[str] = set()
        created_task_keys: set[str] = set()
        replayed_task_keys: set[str] = set()
        unchanged_task_keys: set[str] = set()

        root_task_key = self._make_root_task_key(config, root, request_kind, translator_profile)
        root_record = task_repository.get(root_task_key)
        if root_record is None:
            root_record = self._build_root_task_record(
                config,
                root_task_key,
                root,
                request_kind,
                translator_profile,
            )
            task_repository.save(root_record)

        initial_task_records = task_repository.list_all()
        initially_succeeded_task_keys = {
            task.task_key for task in initial_task_records if task.status == TaskStatus.SUCCEEDED
        }

        run_request = RunRequest(
            run_id=_build_run_id(),
            request_kind=request_kind,
            root=root,
            status="running",
            root_task_key=root_task_key,
        )
        run_repository.save(run_request)
        self._logger.info(
            "Workflow run started: run_id=%s root_task=%s",
            run_request.run_id,
            root_task_key,
        )

        discover_reference_handler = DiscoverReferenceDocumentsTaskHandler()
        discover_translate_handler = DiscoverTranslateDocumentsTaskHandler()
        index_references_handler = IndexMarkdownReferencesTaskHandler()
        merge_reference_indexes_handler = MergeReferenceIndexesTaskHandler()
        discover_translate_fragments_handler = DiscoverTranslateDocumentFragmentsTaskHandler()
        translate_fragment_handler = TranslateFragmentTaskHandler()
        merge_translated_fragments_handler = MergeTranslatedFragmentsTaskHandler()
        revalidator = TaskRevalidator()

        while True:
            task_records = self._revalidate_task_records(
                task_repository.list_all(),
                config,
                task_repository,
                revalidator,
                initially_succeeded_task_keys,
                replayed_task_keys,
                unchanged_task_keys,
            )
            next_task = self._select_next_task(task_records)
            if next_task is None:
                break

            executed_task_keys.add(next_task.task_key)
            self._logger.info(
                "Executing task: key=%s kind=%s status=%s",
                next_task.task_key,
                next_task.spec.kind,
                next_task.status.value,
            )

            if next_task.spec.kind == "discover_reference_documents":
                result = discover_reference_handler.handle(next_task, config, task_repository)
            elif next_task.spec.kind == "discover_translate_documents":
                result = discover_translate_handler.handle(next_task, config, task_repository)
            elif next_task.spec.kind == "index_markdown_references":
                result = index_references_handler.handle(next_task, config)
            elif next_task.spec.kind == "merge_reference_indexes":
                result = merge_reference_indexes_handler.handle(
                    next_task,
                    config,
                    task_repository,
                )
            elif next_task.spec.kind == "discover_translate_document_fragments":
                result = discover_translate_fragments_handler.handle(
                    next_task,
                    config,
                    task_repository,
                )
            elif next_task.spec.kind == "translate_fragment":
                result = translate_fragment_handler.handle(next_task, config)
            elif next_task.spec.kind == "merge_translated_fragments":
                result = merge_translated_fragments_handler.handle(
                    next_task,
                    config,
                    task_repository,
                )
            else:
                raise ValueError(f"Unsupported task kind: {next_task.spec.kind}")

            task_repository.save(result.updated_record)
            self._logger.info(
                "Task completed: key=%s kind=%s new_status=%s",
                result.updated_record.task_key,
                result.updated_record.spec.kind,
                result.updated_record.status.value,
            )
            for new_record in result.new_records:
                task_repository.save(new_record)
                created_task_keys.add(new_record.task_key)
                self._logger.info(
                    "Task created: key=%s kind=%s",
                    new_record.task_key,
                    new_record.spec.kind,
                )

        root_record = task_repository.get(root_task_key)
        run_status = self._resolve_run_status(task_repository.list_all(), root_record)
        completed_run = run_request.model_copy(update={"status": run_status})
        run_repository.save(completed_run)
        summary = WorkflowRunSummary(
            executed_task_count=len(executed_task_keys),
            replayed_task_count=len(replayed_task_keys),
            created_task_count=len(created_task_keys),
            unchanged_task_count=len(unchanged_task_keys),
        )
        self._logger.info(
            "Workflow run summary: executed=%s replayed=%s created=%s unchanged=%s",
            summary.executed_task_count,
            summary.replayed_task_count,
            summary.created_task_count,
            summary.unchanged_task_count,
        )
        self._logger.info(
            "Workflow run finished: run_id=%s status=%s",
            completed_run.run_id,
            completed_run.status,
        )
        return WorkflowRunResult(run_request=completed_run, summary=summary)

    def _build_root_task_record(
        self,
        config: WorkspaceConfig,
        root_task_key: str,
        root: Path,
        request_kind: Literal[
            "reference_index_tree",
            "translate_document_tree",
        ],
        translator_profile: str,
    ) -> TaskRecord:
        if request_kind == "reference_index_tree":
            return TaskRecord(
                task_key=root_task_key,
                spec=DiscoverReferenceDocumentsTaskSpec(root=root),
            )

        if request_kind == "translate_document_tree":
            profile = config.llm.translator.get(translator_profile)
            if profile is None:
                raise KeyError(f"Unknown translator profile: {translator_profile}")
            return TaskRecord(
                task_key=root_task_key,
                spec=DiscoverTranslateDocumentsTaskSpec(
                    root=root,
                    profile_name=translator_profile,
                    profile_digest=make_translator_profile_digest(profile),
                ),
            )

        raise ValueError(f"Unsupported request kind: {request_kind}")

    def _make_root_task_key(
        self,
        config: WorkspaceConfig,
        root: Path,
        request_kind: Literal[
            "reference_index_tree",
            "translate_document_tree",
        ],
        translator_profile: str,
    ) -> str:
        if request_kind == "reference_index_tree":
            return make_discover_reference_documents_task_key(root)
        if request_kind == "translate_document_tree":
            profile = config.llm.translator.get(translator_profile)
            if profile is None:
                raise KeyError(f"Unknown translator profile: {translator_profile}")
            return make_discover_translate_documents_task_key(
                root,
                translator_profile,
                make_translator_profile_digest(profile),
            )
        raise ValueError(f"Unsupported request kind: {request_kind}")

    def _revalidate_task_records(
        self,
        task_records: list[TaskRecord],
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
        revalidator: TaskRevalidator,
        initially_succeeded_task_keys: set[str],
        replayed_task_keys: set[str],
        unchanged_task_keys: set[str],
    ) -> list[TaskRecord]:
        refreshed_records = revalidator.revalidate_all(task_records, config)

        for original_record, refreshed_record in zip(task_records, refreshed_records, strict=False):
            if refreshed_record != original_record:
                task_repository.save(refreshed_record)
                if (
                    original_record.task_key in initially_succeeded_task_keys
                    and refreshed_record.status == TaskStatus.PENDING
                ):
                    replayed_task_keys.add(original_record.task_key)
                    unchanged_task_keys.discard(original_record.task_key)
                self._logger.info(
                    "Task revalidated: key=%s kind=%s old_status=%s new_status=%s",
                    original_record.task_key,
                    original_record.spec.kind,
                    original_record.status.value,
                    refreshed_record.status.value,
                )
            elif original_record.task_key in initially_succeeded_task_keys:
                unchanged_task_keys.add(original_record.task_key)

        return refreshed_records

    def _select_next_task(self, task_records: list[TaskRecord]) -> TaskRecord | None:
        ordered_records = sorted(task_records, key=lambda record: record.task_key)
        task_index = {record.task_key: record for record in task_records}

        for record in ordered_records:
            if record.status == TaskStatus.PENDING:
                return record

        for record in ordered_records:
            if record.status != TaskStatus.WAITING:
                continue

            if self._is_waiting_task_unblocked(record, task_index):
                return record

        return None

    def _is_waiting_task_unblocked(
        self,
        record: TaskRecord,
        task_index: dict[str, TaskRecord],
    ) -> bool:
        for child_task_key in record.child_task_keys:
            child_record = task_index.get(child_task_key)
            if child_record is None:
                continue
            if child_record.status in {TaskStatus.PENDING, TaskStatus.WAITING}:
                return False

        return True

    def _resolve_run_status(
        self,
        task_records: list[TaskRecord],
        root_record: TaskRecord | None,
    ) -> str:
        if any(record.status == TaskStatus.FAILED for record in task_records):
            return "failed"
        if root_record is not None and root_record.status == TaskStatus.SUCCEEDED:
            return "succeeded"
        return "failed"


def _build_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")