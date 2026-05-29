import shutil
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from do_my_work.application.task_keys import (
    make_copy_task_key,
    make_discover_document_fragments_task_key,
    make_merge_fragment_results_task_key,
    make_process_fragment_task_key,
)
from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverDocumentFragmentsTaskSpec,
    DiscoverDocumentsTaskSpec,
    DiscoverSummaryDocumentsTaskSpec,
    MarkdownFragment,
    MergeFragmentResultsTaskSpec,
    ProcessedFragmentResult,
    ProcessFragmentTaskSpec,
    SummarizeMarkdownDocumentTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    WorkspaceConfig,
)
from do_my_work.infrastructure.json_workflow_store import JsonTaskRepository
from do_my_work.infrastructure.markdown_fragment_report import (
    build_summary_report_relative_path,
    extract_markdown_fragments,
    render_fragment_length_line,
    render_fragment_length_report,
    render_fragment_length_report_from_lines,
)


@dataclass(slots=True)
class TaskHandlerResult:
    updated_record: TaskRecord
    new_records: list[TaskRecord] = field(default_factory=list)


class DiscoverDocumentsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, DiscoverDocumentsTaskSpec):
            raise TypeError("discover handler requires a DiscoverDocumentsTaskSpec")

        root_path = config.input_dir / spec.root
        if not root_path.exists():
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Input root does not exist.",
                            error=str(root_path),
                        ),
                    }
                )
            )

        discovered_records: list[TaskRecord] = []
        child_task_keys: list[str] = []

        for source_path in sorted(_iter_markdown_documents(root_path)):
            relative_path = source_path.relative_to(config.input_dir)
            source_digest = _build_source_digest(source_path)
            task_key = make_copy_task_key(relative_path, source_digest)
            child_task_keys.append(task_key)

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=CopyFileTaskSpec(
                            relative_path=relative_path,
                            source_digest=source_digest,
                        ),
                    )
                )

        child_records = [task_repository.get(task_key) for task_key in child_task_keys]
        child_records.extend(discovered_records)

        failed_children = [
            child
            for child in child_records
            if child is not None and child.status == TaskStatus.FAILED
        ]
        all_succeeded = all(
            child is not None and child.status == TaskStatus.SUCCEEDED for child in child_records
        )

        if failed_children:
            status = TaskStatus.FAILED
            message = f"{len(child_task_keys)} documents discovered, at least one copy task failed."
        elif all_succeeded:
            status = TaskStatus.SUCCEEDED
            message = f"{len(child_task_keys)} documents discovered and copied."
        else:
            status = TaskStatus.WAITING
            message = f"{len(child_task_keys)} documents discovered."

        updated_record = record.model_copy(
            update={
                "status": status,
                "child_task_keys": child_task_keys,
                "outcome": TaskOutcome(
                    message=message,
                    created_task_keys=[task.task_key for task in discovered_records],
                ),
            }
        )
        return TaskHandlerResult(updated_record=updated_record, new_records=discovered_records)


class CopyFileTaskHandler:
    def handle(self, record: TaskRecord, config: WorkspaceConfig) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, CopyFileTaskSpec):
            raise TypeError("copy handler requires a CopyFileTaskSpec")

        source_path = config.input_dir / spec.relative_path
        destination_path = config.output_dir / spec.relative_path

        if not source_path.exists():
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Source file does not exist.",
                            error=str(source_path),
                        ),
                    }
                )
            )

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(message="File copied."),
                }
            )
        )


class DiscoverSummaryDocumentsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, DiscoverSummaryDocumentsTaskSpec):
            raise TypeError("discover handler requires a DiscoverSummaryDocumentsTaskSpec")

        root_path = config.input_dir / spec.root
        if not root_path.exists():
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Input root does not exist.",
                            error=str(root_path),
                        ),
                    }
                )
            )

        discovered_records: list[TaskRecord] = []
        child_task_keys: list[str] = []

        for source_path in sorted(_iter_markdown_documents(root_path)):
            relative_path = source_path.relative_to(config.input_dir)
            source_digest = _build_source_digest(source_path)
            task_key = make_discover_document_fragments_task_key(relative_path, source_digest)
            child_task_keys.append(task_key)

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=DiscoverDocumentFragmentsTaskSpec(
                            relative_path=relative_path,
                            source_digest=source_digest,
                        ),
                    )
                )

        child_records = [task_repository.get(task_key) for task_key in child_task_keys]
        child_records.extend(discovered_records)

        failed_children = [
            child
            for child in child_records
            if child is not None and child.status == TaskStatus.FAILED
        ]
        all_succeeded = all(
            child is not None and child.status == TaskStatus.SUCCEEDED for child in child_records
        )

        if failed_children:
            status = TaskStatus.FAILED
            message = (
                f"{len(child_task_keys)} documents discovered, at least one summary task failed."
            )
        elif all_succeeded:
            status = TaskStatus.SUCCEEDED
            message = f"{len(child_task_keys)} documents discovered and summarized."
        else:
            status = TaskStatus.WAITING
            message = f"{len(child_task_keys)} documents discovered."

        updated_record = record.model_copy(
            update={
                "status": status,
                "child_task_keys": child_task_keys,
                "outcome": TaskOutcome(
                    message=message,
                    created_task_keys=[task.task_key for task in discovered_records],
                ),
            }
        )
        return TaskHandlerResult(updated_record=updated_record, new_records=discovered_records)


class DiscoverDocumentFragmentsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, DiscoverDocumentFragmentsTaskSpec):
            raise TypeError(
                "fragment discovery handler requires a "
                "DiscoverDocumentFragmentsTaskSpec"
            )

        source_path = config.input_dir / spec.relative_path
        if not source_path.exists():
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Source file does not exist.",
                            error=str(source_path),
                        ),
                    }
                )
            )

        fragments = extract_markdown_fragments(source_path)
        discovered_records: list[TaskRecord] = []
        fragment_task_keys: list[str] = []

        for fragment in fragments:
            fragment_digest = _build_fragment_digest(fragment)
            task_key = make_process_fragment_task_key(spec.relative_path, fragment_digest)
            fragment_task_keys.append(task_key)

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=ProcessFragmentTaskSpec(
                            document_relative_path=spec.relative_path,
                            fragment_kind=fragment.fragment_kind,
                            heading_path=fragment.heading_path,
                            text=fragment.text,
                            fragment_digest=fragment_digest,
                        ),
                    )
                )

        merge_task_key = make_merge_fragment_results_task_key(
            spec.relative_path,
            spec.source_digest,
        )
        child_task_keys = [*fragment_task_keys, merge_task_key]

        if task_repository.get(merge_task_key) is None:
            discovered_records.append(
                TaskRecord(
                    task_key=merge_task_key,
                    spec=MergeFragmentResultsTaskSpec(
                        document_relative_path=spec.relative_path,
                        source_digest=spec.source_digest,
                        fragment_task_keys=fragment_task_keys,
                    ),
                    child_task_keys=fragment_task_keys,
                )
            )

        child_records = [task_repository.get(task_key) for task_key in child_task_keys]
        child_records.extend(
            task for task in discovered_records if task.task_key in set(child_task_keys)
        )

        failed_children = [
            child
            for child in child_records
            if child is not None and child.status == TaskStatus.FAILED
        ]
        all_succeeded = all(
            child is not None and child.status == TaskStatus.SUCCEEDED for child in child_records
        )

        if failed_children:
            status = TaskStatus.FAILED
            message = (
                f"{len(fragment_task_keys)} fragments discovered, "
                "at least one fragment task failed."
            )
        elif all_succeeded:
            status = TaskStatus.SUCCEEDED
            message = f"{len(fragment_task_keys)} fragments discovered and merged."
        else:
            status = TaskStatus.WAITING
            message = f"{len(fragment_task_keys)} fragments discovered."

        updated_record = record.model_copy(
            update={
                "status": status,
                "child_task_keys": child_task_keys,
                "outcome": TaskOutcome(
                    message=message,
                    created_task_keys=[task.task_key for task in discovered_records],
                ),
            }
        )
        return TaskHandlerResult(updated_record=updated_record, new_records=discovered_records)


class ProcessFragmentTaskHandler:
    def handle(self, record: TaskRecord, config: WorkspaceConfig) -> TaskHandlerResult:
        del config
        spec = record.spec
        if not isinstance(spec, ProcessFragmentTaskSpec):
            raise TypeError("fragment processor requires a ProcessFragmentTaskSpec")

        fragment = MarkdownFragment(
            fragment_kind=spec.fragment_kind,
            heading_path=spec.heading_path,
            text=spec.text,
            length=len(spec.text),
        )
        rendered_text = render_fragment_length_line(fragment)

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(
                        message="Fragment processed.",
                        result=ProcessedFragmentResult(
                            rendered_text=rendered_text,
                            length=fragment.length,
                        ),
                    ),
                }
            )
        )


class MergeFragmentResultsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, MergeFragmentResultsTaskSpec):
            raise TypeError("fragment merge handler requires a MergeFragmentResultsTaskSpec")

        fragment_records = [task_repository.get(task_key) for task_key in spec.fragment_task_keys]
        if any(fragment_record is None for fragment_record in fragment_records):
            missing_task_keys = [
                task_key
                for task_key, fragment_record in zip(
                    spec.fragment_task_keys,
                    fragment_records,
                    strict=False,
                )
                if fragment_record is None
            ]
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Fragment task record is missing.",
                            error=", ".join(missing_task_keys),
                        ),
                    }
                )
            )

        failed_fragments = [
            fragment_record
            for fragment_record in fragment_records
            if fragment_record is not None and fragment_record.status == TaskStatus.FAILED
        ]
        if failed_fragments:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="At least one fragment task failed.",
                        ),
                    }
                )
            )

        if not all(
            fragment_record is not None and fragment_record.status == TaskStatus.SUCCEEDED
            for fragment_record in fragment_records
        ):
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.WAITING,
                        "outcome": TaskOutcome(
                            message="Waiting for fragment results.",
                        ),
                    }
                )
            )

        processed_lines: list[str] = []
        for fragment_record in fragment_records:
            if (
                fragment_record is None
                or fragment_record.outcome is None
                or fragment_record.outcome.result is None
            ):
                return TaskHandlerResult(
                    updated_record=record.model_copy(
                        update={
                            "status": TaskStatus.FAILED,
                            "outcome": TaskOutcome(
                                message="Fragment task did not publish a result.",
                            ),
                        }
                    )
                )

            processed_lines.append(fragment_record.outcome.result.rendered_text)

        report = render_fragment_length_report_from_lines(
            relative_source=spec.document_relative_path.as_posix(),
            processed_lines=processed_lines,
            header_text=spec.header_text,
            footer_text=spec.footer_text,
        )
        destination_path = config.output_dir / build_summary_report_relative_path(
            spec.document_relative_path
        )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(report, encoding="utf-8")

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(message="Fragment length report written."),
                }
            )
        )


class SummarizeMarkdownDocumentTaskHandler:
    def handle(self, record: TaskRecord, config: WorkspaceConfig) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, SummarizeMarkdownDocumentTaskSpec):
            raise TypeError("summary handler requires a SummarizeMarkdownDocumentTaskSpec")

        source_path = config.input_dir / spec.relative_path
        destination_path = config.output_dir / build_summary_report_relative_path(
            spec.relative_path
        )

        if not source_path.exists():
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Source file does not exist.",
                            error=str(source_path),
                        ),
                    }
                )
            )

        report = render_fragment_length_report(source_path, config.input_dir)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(report, encoding="utf-8")

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(message="Fragment length report written."),
                }
            )
        )


def _build_source_digest(path: Path) -> str:
    digest = sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _build_fragment_digest(fragment: MarkdownFragment) -> str:
    payload = "|".join(
        [fragment.fragment_kind, *fragment.heading_path, fragment.text]
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _iter_markdown_documents(root_path: Path) -> list[Path]:
    return [
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() == ".md"
    ]