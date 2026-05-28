from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverDocumentsTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    WorkspaceConfig,
)


class TaskRevalidator:
    def revalidate_all(
        self,
        task_records: list[TaskRecord],
        config: WorkspaceConfig,
    ) -> list[TaskRecord]:
        task_index = {record.task_key: record for record in task_records}

        for record in sorted(task_records, key=_revalidation_priority):
            refreshed_record = self.revalidate(record, config, task_index)
            task_index[record.task_key] = refreshed_record

        return [task_index[record.task_key] for record in task_records]

    def revalidate(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_index: dict[str, TaskRecord],
    ) -> TaskRecord:
        spec = record.spec

        if isinstance(spec, CopyFileTaskSpec):
            return self._revalidate_copy_file(record, config)

        if isinstance(spec, DiscoverDocumentsTaskSpec):
            return self._revalidate_discover_documents(record, task_index)

        return record

    def _revalidate_copy_file(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
    ) -> TaskRecord:
        if record.status != TaskStatus.SUCCEEDED:
            return record

        destination_path = config.output_dir / record.spec.relative_path
        if destination_path.exists():
            return record

        return record.model_copy(
            update={
                "status": TaskStatus.PENDING,
                "outcome": TaskOutcome(
                    message="Output file is missing; task must run again.",
                ),
            }
        )

    def _revalidate_discover_documents(
        self,
        record: TaskRecord,
        task_index: dict[str, TaskRecord],
    ) -> TaskRecord:
        if record.status != TaskStatus.SUCCEEDED:
            return record

        child_records = [task_index.get(task_key) for task_key in record.child_task_keys]
        if all(
            child is not None and child.status == TaskStatus.SUCCEEDED
            for child in child_records
        ):
            return record

        created_task_keys = []
        if record.outcome is not None:
            created_task_keys = record.outcome.created_task_keys

        return record.model_copy(
            update={
                "status": TaskStatus.WAITING,
                "outcome": TaskOutcome(
                    message=f"{len(record.child_task_keys)} documents discovered.",
                    created_task_keys=created_task_keys,
                ),
            }
        )


def _revalidation_priority(record: TaskRecord) -> tuple[int, str]:
    priority = 1
    if record.spec.kind == "copy_file":
        priority = 0
    return (priority, record.task_key)