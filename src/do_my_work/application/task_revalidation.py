from do_my_work.domain.models import (
    DiscoverReferenceDocumentsTaskSpec,
    DiscoverTranslateDocumentFragmentsTaskSpec,
    DiscoverTranslateDocumentsTaskSpec,
    IndexMarkdownReferencesTaskSpec,
    MergeReferenceIndexesTaskSpec,
    MergeTranslatedFragmentsTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    TranslateFragmentTaskSpec,
    WorkspaceConfig,
)
from do_my_work.infrastructure.markdown_reference_report import (
    build_reference_report_relative_path,
    build_root_reference_index_path,
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

        if isinstance(spec, IndexMarkdownReferencesTaskSpec):
            return self._revalidate_reference_index(record, config)

        if isinstance(spec, TranslateFragmentTaskSpec):
            return self._revalidate_translate_fragment(record)

        if isinstance(spec, MergeReferenceIndexesTaskSpec):
            return self._revalidate_merge_reference_indexes(record, config, task_index)

        if isinstance(spec, MergeTranslatedFragmentsTaskSpec):
            return self._revalidate_merge_translated_fragments(record, config, task_index)

        if isinstance(spec, DiscoverReferenceDocumentsTaskSpec):
            return self._revalidate_discover_reference_documents(record, task_index)

        if isinstance(spec, DiscoverTranslateDocumentFragmentsTaskSpec):
            return self._revalidate_discover_translate_document_fragments(record, task_index)

        if isinstance(spec, DiscoverTranslateDocumentsTaskSpec):
            return self._revalidate_discover_translate_documents(record, task_index)

        return record

    def _revalidate_reference_index(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
    ) -> TaskRecord:
        if record.status != TaskStatus.SUCCEEDED:
            return record

        destination_path = config.output_dir / build_reference_report_relative_path(
            record.spec.relative_path
        )
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

    def _revalidate_discover_reference_documents(
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
                    message=(
                        f"{max(len(record.child_task_keys) - 1, 0)} documents discovered."
                    ),
                    created_task_keys=created_task_keys,
                ),
            }
        )

    def _revalidate_merge_reference_indexes(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_index: dict[str, TaskRecord],
    ) -> TaskRecord:
        child_records = [task_index.get(task_key) for task_key in record.spec.reference_task_keys]
        if not all(
            child is not None and child.status == TaskStatus.SUCCEEDED
            for child in child_records
        ):
            return record.model_copy(
                update={
                    "status": TaskStatus.WAITING,
                    "outcome": TaskOutcome(
                        message="Waiting for reference index results.",
                    ),
                }
            )

        destination_path = config.output_dir / build_root_reference_index_path()
        if record.status == TaskStatus.SUCCEEDED and destination_path.exists():
            return record

        return record.model_copy(
            update={
                "status": TaskStatus.PENDING,
                "outcome": TaskOutcome(
                    message="Output file is missing; task must run again.",
                ),
            }
        )

    def _revalidate_discover_translate_document_fragments(
        self,
        record: TaskRecord,
        task_index: dict[str, TaskRecord],
    ) -> TaskRecord:
        if record.status not in {TaskStatus.SUCCEEDED, TaskStatus.WAITING, TaskStatus.FAILED}:
            return record

        if not record.child_task_keys:
            return record

        child_records = [task_index.get(task_key) for task_key in record.child_task_keys]
        failed_children = [
            child
            for child in child_records
            if child is not None and child.status == TaskStatus.FAILED
        ]
        if failed_children:
            created_task_keys = []
            if record.outcome is not None:
                created_task_keys = record.outcome.created_task_keys

            fragment_task_count = max(len(record.child_task_keys) - 1, 0)
            return record.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "outcome": TaskOutcome(
                        message=(
                            f"{fragment_task_count} fragments discovered, "
                            "at least one translation task failed."
                        ),
                        created_task_keys=created_task_keys,
                    ),
                }
            )

        if all(
            child is not None and child.status == TaskStatus.SUCCEEDED
            for child in child_records
        ):
            created_task_keys = []
            if record.outcome is not None:
                created_task_keys = record.outcome.created_task_keys

            fragment_task_count = max(len(record.child_task_keys) - 1, 0)
            return record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(
                        message=(
                            f"{fragment_task_count} fragments discovered and translated."
                        ),
                        created_task_keys=created_task_keys,
                    ),
                }
            )

        created_task_keys = []
        if record.outcome is not None:
            created_task_keys = record.outcome.created_task_keys

        fragment_task_count = max(len(record.child_task_keys) - 1, 0)
        return record.model_copy(
            update={
                "status": TaskStatus.WAITING,
                "outcome": TaskOutcome(
                    message=f"{fragment_task_count} fragments discovered.",
                    created_task_keys=created_task_keys,
                ),
            }
        )

    def _revalidate_merge_translated_fragments(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_index: dict[str, TaskRecord],
    ) -> TaskRecord:
        if record.status not in {TaskStatus.SUCCEEDED, TaskStatus.WAITING, TaskStatus.FAILED}:
            return record

        child_records = [task_index.get(task_key) for task_key in record.spec.fragment_task_keys]
        if any(
            child is not None and child.status == TaskStatus.FAILED for child in child_records
        ):
            return record.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "outcome": TaskOutcome(
                        message="At least one fragment task failed.",
                    ),
                }
            )

        if not all(
            child is not None and child.status == TaskStatus.SUCCEEDED
            for child in child_records
        ):
            return record.model_copy(
                update={
                    "status": TaskStatus.WAITING,
                    "outcome": TaskOutcome(
                        message="Waiting for fragment results.",
                    ),
                }
            )

        destination_path = config.output_dir / record.spec.document_relative_path
        if record.status == TaskStatus.SUCCEEDED and destination_path.exists():
            return record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(message="Translated document written."),
                }
            )

        return record.model_copy(
            update={
                "status": TaskStatus.PENDING,
                "outcome": TaskOutcome(
                    message="Output file is missing; task must run again.",
                ),
            }
        )

    def _revalidate_discover_translate_documents(
        self,
        record: TaskRecord,
        task_index: dict[str, TaskRecord],
    ) -> TaskRecord:
        if record.status not in {TaskStatus.SUCCEEDED, TaskStatus.WAITING, TaskStatus.FAILED}:
            return record

        if not record.child_task_keys:
            return record

        child_records = [task_index.get(task_key) for task_key in record.child_task_keys]
        failed_children = [
            child
            for child in child_records
            if child is not None and child.status == TaskStatus.FAILED
        ]
        if failed_children:
            created_task_keys = []
            if record.outcome is not None:
                created_task_keys = record.outcome.created_task_keys

            return record.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "outcome": TaskOutcome(
                        message=(
                            f"{len(record.child_task_keys)} documents discovered, "
                            "at least one translation task failed."
                        ),
                        created_task_keys=created_task_keys,
                    ),
                }
            )

        if all(
            child is not None and child.status == TaskStatus.SUCCEEDED
            for child in child_records
        ):
            created_task_keys = []
            if record.outcome is not None:
                created_task_keys = record.outcome.created_task_keys

            return record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(
                        message=(
                            f"{len(record.child_task_keys)} documents discovered and "
                            "translated."
                        ),
                        created_task_keys=created_task_keys,
                    ),
                }
            )

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

    def _revalidate_translate_fragment(self, record: TaskRecord) -> TaskRecord:
        if record.status != TaskStatus.FAILED:
            return record

        return record.model_copy(
            update={
                "status": TaskStatus.PENDING,
                "outcome": TaskOutcome(
                    message="Previous failed translation will be retried.",
                ),
            }
        )


def _revalidation_priority(record: TaskRecord) -> tuple[int, str]:
    priority = 2
    if record.spec.kind in {"index_markdown_references", "translate_fragment"}:
        priority = 0
    elif record.spec.kind in {"merge_reference_indexes", "merge_translated_fragments"}:
        priority = 1
    return (priority, record.task_key)