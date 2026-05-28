import logging
from datetime import UTC, datetime
from pathlib import Path

from do_my_work.application.task_handlers import CopyFileTaskHandler, DiscoverDocumentsTaskHandler
from do_my_work.application.task_keys import make_discover_documents_task_key
from do_my_work.application.task_revalidation import TaskRevalidator
from do_my_work.domain.models import (
    DiscoverDocumentsTaskSpec,
    RunRequest,
    TaskRecord,
    TaskStatus,
    WorkspaceConfig,
)
from do_my_work.infrastructure.json_workflow_store import JsonRunRepository, JsonTaskRepository


class WorkflowEngine:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def run(self, config: WorkspaceConfig, root: Path = Path(".")) -> RunRequest:
        task_repository = JsonTaskRepository(config.data_dir / "tasks")
        run_repository = JsonRunRepository(config.data_dir / "runs")

        root_task_key = make_discover_documents_task_key(root)
        root_record = task_repository.get(root_task_key)
        if root_record is None:
            root_record = TaskRecord(
                task_key=root_task_key,
                spec=DiscoverDocumentsTaskSpec(root=root),
            )
            task_repository.save(root_record)

        run_request = RunRequest(
            run_id=_build_run_id(),
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

        discover_handler = DiscoverDocumentsTaskHandler()
        copy_handler = CopyFileTaskHandler()
        revalidator = TaskRevalidator()

        while True:
            task_records = self._revalidate_task_records(
                task_repository.list_all(),
                config,
                task_repository,
                revalidator,
            )
            next_task = self._select_next_task(task_records)
            if next_task is None:
                break

            self._logger.info(
                "Executing task: key=%s kind=%s status=%s",
                next_task.task_key,
                next_task.spec.kind,
                next_task.status.value,
            )

            if next_task.spec.kind == "discover_documents":
                result = discover_handler.handle(next_task, config, task_repository)
            else:
                result = copy_handler.handle(next_task, config)

            task_repository.save(result.updated_record)
            self._logger.info(
                "Task completed: key=%s kind=%s new_status=%s",
                result.updated_record.task_key,
                result.updated_record.spec.kind,
                result.updated_record.status.value,
            )
            for new_record in result.new_records:
                task_repository.save(new_record)
                self._logger.info(
                    "Task created: key=%s kind=%s",
                    new_record.task_key,
                    new_record.spec.kind,
                )

        root_record = task_repository.get(root_task_key)
        run_status = self._resolve_run_status(task_repository.list_all(), root_record)
        completed_run = run_request.model_copy(update={"status": run_status})
        run_repository.save(completed_run)
        self._logger.info(
            "Workflow run finished: run_id=%s status=%s",
            completed_run.run_id,
            completed_run.status,
        )
        return completed_run

    def _revalidate_task_records(
        self,
        task_records: list[TaskRecord],
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
        revalidator: TaskRevalidator,
    ) -> list[TaskRecord]:
        refreshed_records = revalidator.revalidate_all(task_records, config)

        for original_record, refreshed_record in zip(task_records, refreshed_records, strict=False):
            if refreshed_record != original_record:
                task_repository.save(refreshed_record)
                self._logger.info(
                    "Task revalidated: key=%s kind=%s old_status=%s new_status=%s",
                    original_record.task_key,
                    original_record.spec.kind,
                    original_record.status.value,
                    refreshed_record.status.value,
                )

        return refreshed_records

    def _select_next_task(self, task_records: list[TaskRecord]) -> TaskRecord | None:
        ordered_records = sorted(task_records, key=lambda record: record.task_key)

        for status in (TaskStatus.PENDING, TaskStatus.WAITING):
            for record in ordered_records:
                if record.status == status:
                    return record

        return None

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