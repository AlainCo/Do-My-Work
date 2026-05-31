from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
import shutil
from statistics import pvariance
import textwrap
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from trafilatura import bare_extraction, extract

from do_my_work.application.task_keys import (
    make_check_reference_url_task_key,
    make_copy_resource_file_task_key,
    make_discover_copy_resources_task_key,
    make_discover_translate_document_fragments_task_key,
    make_index_markdown_references_task_key,
    make_merge_reference_indexes_task_key,
    make_merge_translated_fragments_task_key,
    make_translation_plan_digest,
    make_translate_fragment_task_key,
    make_translated_document_render_digest,
    make_translated_document_render_digest_for_content,
    make_translator_profile_digest,
)
from do_my_work.domain.models import (
    CheckReferenceUrlTaskSpec,
    CopyResourceFileTaskSpec,
    DiscoverCopyResourcesTaskSpec,
    DiscoverReferenceDocumentsTaskSpec,
    DiscoverTranslateDocumentFragmentsTaskSpec,
    DiscoverTranslateDocumentsTaskSpec,
    IndexMarkdownReferencesTaskSpec,
    LocalWorkflowConfig,
    MarkdownFragment,
    ReferenceIndexSidecar,
    ReferenceUrlCheckResult,
    ReferenceUrlIndexEntry,
    ReferenceUrlOccurrence,
    MergeReferenceIndexesTaskSpec,
    MergeTranslatedFragmentsTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    TranslatedFragmentResult,
    TranslatorProfileConfig,
    TranslateFragmentTaskSpec,
    WorkspaceConfig,
)
from do_my_work.infrastructure.config_loader import (
    LOCAL_WORKFLOW_CONFIG_NAME,
    load_local_workflow_config,
)
from do_my_work.infrastructure.json_workflow_store import JsonTaskRepository
from do_my_work.infrastructure.markdown_fragment_report import (
    build_translation_review_path,
    extract_markdown_fragments,
    render_chunk_review_document,
    render_markdown_fragment,
    render_translated_document,
)
from do_my_work.infrastructure.markdown_reference_report import (
    build_reference_report_relative_path,
    build_root_reference_index_path,
    build_root_reference_index_yaml_path,
    extract_markdown_references,
    is_public_reference_url,
    render_markdown_reference_report,
    render_tree_markdown_reference_report,
)
from do_my_work.infrastructure.ollama_client import (
    AbstractLlmClient,
    LlmCallTimingSummary,
    UnsupportedLlmProviderError,
    build_llm_client,
)
from do_my_work.infrastructure.reference_index_sidecar import (
    load_reference_index_sidecar,
    write_reference_index_sidecar,
)


@dataclass(slots=True)
class TaskHandlerResult:
    updated_record: TaskRecord
    new_records: list[TaskRecord] = field(default_factory=list)


@dataclass(slots=True)
class TranslationChunk:
    start_index: int
    end_index: int
    input_markdown: str
    pre_context: str
    post_context: str
    fragment_digest: str
    translation_input_digest: str
    first_fragment: MarkdownFragment


@dataclass(frozen=True, slots=True)
class DocumentWorkflowSettings:
    source_path: Path
    relative_path: Path
    translation_profile_name: str | None = None
    translation_hints: str = ""
    translated_document_header: str | None = None
    translated_document_footer: str | None = None


class DiscoverReferenceDocumentsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, DiscoverReferenceDocumentsTaskSpec):
            raise TypeError("discover handler requires a DiscoverReferenceDocumentsTaskSpec")

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
        document_relative_paths: list[Path] = []
        child_task_keys: list[str] = []
        discovered_urls: set[str] = set()

        for document in sorted(
            _iter_markdown_documents(root_path, config, workflow_kind="reference_index_tree"),
            key=lambda item: item.relative_path.as_posix(),
        ):
            source_path = document.source_path
            relative_path = document.relative_path
            document_relative_paths.append(relative_path)
            source_digest = _build_source_digest(source_path)
            task_key = make_index_markdown_references_task_key(relative_path, source_digest)
            child_task_keys.append(task_key)

            if spec.check_urls:
                discovered_urls.update(
                    reference.url
                    for reference in extract_markdown_references(source_path)
                    if is_public_reference_url(reference.url)
                )

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=IndexMarkdownReferencesTaskSpec(
                            relative_path=relative_path,
                            source_digest=source_digest,
                        ),
                    )
                )

        url_check_task_keys: list[str] = []
        reusable_url_entries = _load_reference_index_entries(config.output_dir)
        if spec.check_urls:
            for url in sorted(discovered_urls):
                reusable_entry = reusable_url_entries.get(url)
                if reusable_entry is not None and reusable_entry.skip_recheck:
                    continue
                task_key = make_check_reference_url_task_key(url, spec.url_check_run_token)
                url_check_task_keys.append(task_key)
                child_task_keys.append(task_key)

                if task_repository.get(task_key) is None:
                    discovered_records.append(
                        TaskRecord(
                            task_key=task_key,
                            spec=CheckReferenceUrlTaskSpec(
                                url=url,
                                url_check_run_token=spec.url_check_run_token,
                            ),
                        )
                    )

        merge_task_key = make_merge_reference_indexes_task_key(
            spec.root,
            document_relative_paths,
            checked_urls=sorted(discovered_urls) if spec.check_urls else None,
            url_check_run_token=spec.url_check_run_token,
        )
        child_task_keys.append(merge_task_key)
        if task_repository.get(merge_task_key) is None:
            discovered_records.append(
                TaskRecord(
                    task_key=merge_task_key,
                    spec=MergeReferenceIndexesTaskSpec(
                        root=spec.root,
                        document_relative_paths=document_relative_paths,
                        reference_task_keys=[
                            make_index_markdown_references_task_key(
                                relative_path,
                                _build_source_digest(config.input_dir / relative_path),
                            )
                            for relative_path in document_relative_paths
                        ],
                        url_check_task_keys=url_check_task_keys,
                        url_check_run_token=spec.url_check_run_token,
                    ),
                    child_task_keys=[
                        make_index_markdown_references_task_key(
                            relative_path,
                            _build_source_digest(config.input_dir / relative_path),
                        )
                        for relative_path in document_relative_paths
                    ]
                    + url_check_task_keys,
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
                f"{len(document_relative_paths)} documents discovered, "
                "at least one reference task failed."
            )
        elif all_succeeded:
            status = TaskStatus.SUCCEEDED
            message = f"{len(document_relative_paths)} documents discovered and indexed."
        else:
            status = TaskStatus.WAITING
            message = f"{len(document_relative_paths)} documents discovered."

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


class DiscoverCopyResourcesTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, DiscoverCopyResourcesTaskSpec):
            raise TypeError("discover handler requires a DiscoverCopyResourcesTaskSpec")

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

        for source_path in sorted(
            _iter_resource_files(root_path, config),
            key=lambda path: path.relative_to(config.input_dir).as_posix(),
        ):
            relative_path = source_path.relative_to(config.input_dir)
            source_digest = _build_source_digest(source_path)
            task_key = make_copy_resource_file_task_key(relative_path, source_digest)
            child_task_keys.append(task_key)

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=CopyResourceFileTaskSpec(
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
                f"{len(child_task_keys)} resources discovered, "
                "at least one copy task failed."
            )
        elif all_succeeded:
            status = TaskStatus.SUCCEEDED
            message = f"{len(child_task_keys)} resources discovered and copied."
        else:
            status = TaskStatus.WAITING
            message = f"{len(child_task_keys)} resources discovered."

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


class DiscoverTranslateDocumentsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, DiscoverTranslateDocumentsTaskSpec):
            raise TypeError("discover handler requires a DiscoverTranslateDocumentsTaskSpec")

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

        profile = config.llm.translator.get(spec.profile_name)
        if profile is None:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Translator profile does not exist.",
                            error=spec.profile_name,
                        ),
                    }
                )
            )

        discovered_records: list[TaskRecord] = []
        child_task_keys: list[str] = []

        for document in sorted(
            _iter_markdown_documents(
                root_path,
                config,
                workflow_kind="translate_document_tree",
                default_translation_profile_name=spec.profile_name,
            ),
            key=lambda item: item.relative_path.as_posix(),
        ):
            source_path = document.source_path
            relative_path = document.relative_path
            effective_profile_name = document.translation_profile_name or spec.profile_name
            effective_profile = config.llm.translator.get(effective_profile_name)
            if effective_profile is None:
                return TaskHandlerResult(
                    updated_record=record.model_copy(
                        update={
                            "status": TaskStatus.FAILED,
                            "outcome": TaskOutcome(
                                message="Translator profile does not exist.",
                                error=(
                                    f"{effective_profile_name} for {relative_path.as_posix()}"
                                ),
                            ),
                        }
                    )
                )

            profile_digest = make_translator_profile_digest(effective_profile)
            plan_digest = make_translation_plan_digest(effective_profile)
            effective_header = document.translated_document_header
            if effective_header is None:
                effective_header = effective_profile.translated_document_header
            effective_footer = document.translated_document_footer
            if effective_footer is None:
                effective_footer = effective_profile.translated_document_footer

            render_digest = make_translated_document_render_digest_for_content(
                effective_header,
                effective_footer,
                with_review=spec.with_review,
                translated_first=config.translation_review.translated_first,
            )
            translation_hints_digest = _build_optional_text_digest(document.translation_hints)
            source_digest = _build_source_digest(source_path)
            task_key = make_discover_translate_document_fragments_task_key(
                relative_path,
                source_digest,
                effective_profile_name,
                profile_digest,
                plan_digest,
                render_digest,
                translation_hints_digest,
            )
            child_task_keys.append(task_key)

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
                            relative_path=relative_path,
                            source_digest=source_digest,
                            profile_name=effective_profile_name,
                            profile_digest=profile_digest,
                            plan_digest=plan_digest,
                            render_digest=render_digest,
                            with_review=spec.with_review,
                            translation_hints=document.translation_hints,
                            translation_hints_digest=translation_hints_digest,
                            translated_document_header=effective_header,
                            translated_document_footer=effective_footer,
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
                f"{len(child_task_keys)} documents discovered, "
                "at least one translation task failed."
            )
        elif all_succeeded:
            status = TaskStatus.SUCCEEDED
            message = f"{len(child_task_keys)} documents discovered and translated."
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


class IndexMarkdownReferencesTaskHandler:
    def handle(self, record: TaskRecord, config: WorkspaceConfig) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, IndexMarkdownReferencesTaskSpec):
            raise TypeError("reference indexer requires an IndexMarkdownReferencesTaskSpec")

        source_path = config.input_dir / spec.relative_path
        destination_path = config.output_dir / build_reference_report_relative_path(
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

        report = render_markdown_reference_report(source_path, config.input_dir)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(report, encoding="utf-8")

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(message="Markdown reference report written."),
                }
            )
        )


class CheckReferenceUrlTaskHandler:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client
        self._owned_http_client: httpx.Client | None = None

    def close(self) -> None:
        if self._owned_http_client is not None:
            self._owned_http_client.close()
            self._owned_http_client = None

    def _get_http_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        if self._owned_http_client is None:
            self._owned_http_client = httpx.Client(verify=False)
        return self._owned_http_client

    def handle(self, record: TaskRecord, config: WorkspaceConfig) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, CheckReferenceUrlTaskSpec):
            raise TypeError("URL checker requires a CheckReferenceUrlTaskSpec")

        client = self._get_http_client()
        try:
            with client.stream(
                "GET",
                spec.url,
                follow_redirects=True,
                timeout=20.0,
                headers={"Accept": "text/html,*/*", "Range": f"bytes=0-{_HTML_PREVIEW_BYTE_LIMIT - 1}"},
            ) as response:
                html_title = None
                html_excerpt = None
                html_doi = ""
                pdf_title = None
                pdf_author = None
                pdf_subject = None
                pdf_preview_status = None
                pdf_preview_max_bytes = None
                pdf_excerpt = None
                if not response.is_error and _response_looks_like_pdf(response, spec.url):
                    (
                        pdf_title,
                        pdf_author,
                        pdf_subject,
                        pdf_preview_status,
                        pdf_preview_max_bytes,
                        pdf_excerpt,
                    ) = _extract_pdf_preview(
                        client,
                        spec.url,
                        config.reference_index.max_pdf_bytes,
                        preview_max_text_chars=config.reference_index.preview_max_text_chars,
                        preview_max_lines=config.reference_index.preview_max_lines,
                    )
                else:
                    html_title, html_excerpt, html_doi = _extract_html_preview(
                        response,
                        preview_max_text_chars=config.reference_index.preview_max_text_chars,
                        preview_max_lines=config.reference_index.preview_max_lines,
                    )
                result = ReferenceUrlCheckResult(
                    url=spec.url,
                    checked_at=_build_checked_at_timestamp(),
                    doi=_extract_doi_from_candidates(
                        _extract_doi_from_reference_urls(spec.url, str(response.url)),
                        html_doi,
                    ),
                    redirect_location=_extract_redirect_location(response),
                    final_url=str(response.url),
                    content_type=response.headers.get("content-type"),
                    filename=_resolve_reference_url_filename(spec.url, response),
                    reason_phrase=response.reason_phrase or None,
                    html_title=html_title,
                    html_excerpt=html_excerpt,
                    pdf_title=pdf_title,
                    pdf_author=pdf_author,
                    pdf_subject=pdf_subject,
                    pdf_preview_status=pdf_preview_status,
                    pdf_preview_max_bytes=pdf_preview_max_bytes,
                    pdf_excerpt=pdf_excerpt,
                )
                if response.is_error:
                    return TaskHandlerResult(
                        updated_record=record.model_copy(
                            update={
                                "status": TaskStatus.SUCCEEDED,
                                "outcome": TaskOutcome(
                                    message="URL check recorded an HTTP error status.",
                                    error=response.reason_phrase or f"HTTP {response.status_code}",
                                    error_category="http_status",
                                    http_status_code=response.status_code,
                                    result=result,
                                ),
                            }
                        )
                    )
                return TaskHandlerResult(
                    updated_record=record.model_copy(
                        update={
                            "status": TaskStatus.SUCCEEDED,
                            "outcome": TaskOutcome(
                                message="URL checked.",
                                http_status_code=response.status_code,
                                result=result,
                            ),
                        }
                    )
                )
        except httpx.TimeoutException as exc:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.SUCCEEDED,
                        "outcome": TaskOutcome(
                            message="URL check recorded a timeout.",
                            error=str(exc),
                            error_category="timeout",
                            result=ReferenceUrlCheckResult(
                                url=spec.url,
                                checked_at=_build_checked_at_timestamp(),
                                doi=_extract_doi_from_reference_urls(spec.url),
                                filename=_resolve_reference_url_filename(spec.url, None),
                            ),
                        ),
                    }
                )
            )
        except httpx.RequestError as exc:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.SUCCEEDED,
                        "outcome": TaskOutcome(
                            message="URL check recorded a request error.",
                            error=str(exc),
                            error_category="request_error",
                            result=ReferenceUrlCheckResult(
                                url=spec.url,
                                checked_at=_build_checked_at_timestamp(),
                                doi=_extract_doi_from_reference_urls(spec.url),
                                filename=_resolve_reference_url_filename(spec.url, None),
                            ),
                        ),
                    }
                )
            )


class CopyResourceFileTaskHandler:
    def handle(self, record: TaskRecord, config: WorkspaceConfig) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, CopyResourceFileTaskSpec):
            raise TypeError("resource copier requires a CopyResourceFileTaskSpec")

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
                    "outcome": TaskOutcome(message="Resource copied."),
                }
            )
        )


class MergeReferenceIndexesTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, MergeReferenceIndexesTaskSpec):
            raise TypeError("reference merge handler requires a MergeReferenceIndexesTaskSpec")

        reference_records = [task_repository.get(task_key) for task_key in spec.reference_task_keys]
        if any(reference_record is None for reference_record in reference_records):
            missing_task_keys = [
                task_key
                for task_key, reference_record in zip(
                    spec.reference_task_keys,
                    reference_records,
                    strict=False,
                )
                if reference_record is None
            ]
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Reference task record is missing.",
                            error=", ".join(missing_task_keys),
                        ),
                    }
                )
            )

        if any(
            reference_record is not None and reference_record.status == TaskStatus.FAILED
            for reference_record in reference_records
        ):
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="At least one reference task failed.",
                        ),
                    }
                )
            )

        if not all(
            reference_record is not None and reference_record.status == TaskStatus.SUCCEEDED
            for reference_record in reference_records
        ):
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.WAITING,
                        "outcome": TaskOutcome(
                            message="Waiting for reference index results.",
                        ),
                    }
                )
            )

        url_check_records = [task_repository.get(task_key) for task_key in spec.url_check_task_keys]
        if any(url_check_record is None for url_check_record in url_check_records):
            missing_task_keys = [
                task_key
                for task_key, url_check_record in zip(
                    spec.url_check_task_keys,
                    url_check_records,
                    strict=False,
                )
                if url_check_record is None
            ]
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="URL check task record is missing.",
                            error=", ".join(missing_task_keys),
                        ),
                    }
                )
            )

        if not all(
            url_check_record is not None
            and url_check_record.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}
            for url_check_record in url_check_records
        ):
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.WAITING,
                        "outcome": TaskOutcome(
                            message="Waiting for URL check results.",
                        ),
                    }
                )
            )

        url_check_results: dict[str, tuple[ReferenceUrlCheckResult | None, str | None, int | None]] = {}
        for url_check_record in url_check_records:
            if url_check_record is None:
                continue
            if not isinstance(url_check_record.spec, CheckReferenceUrlTaskSpec):
                continue
            result = None
            error_category = None
            http_status_code = None
            if url_check_record.outcome is not None:
                if isinstance(url_check_record.outcome.result, ReferenceUrlCheckResult):
                    result = url_check_record.outcome.result
                error_category = url_check_record.outcome.error_category
                http_status_code = url_check_record.outcome.http_status_code
            url_check_results[url_check_record.spec.url] = (
                result,
                error_category,
                http_status_code,
            )

        sidecar_path = config.output_dir / build_root_reference_index_yaml_path()
        merged_sidecar = _merge_reference_index_sidecar(
            load_reference_index_sidecar(sidecar_path),
            _build_reference_url_occurrences(config.input_dir, spec.document_relative_paths),
            url_check_results,
        )
        write_reference_index_sidecar(sidecar_path, merged_sidecar)
        url_index_entries = {entry.url: entry for entry in merged_sidecar.urls if not entry.unused}

        destination_path = config.output_dir / build_root_reference_index_path()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            render_tree_markdown_reference_report(
                config.input_dir,
                spec.document_relative_paths,
                url_index_entries=url_index_entries or None,
            ),
            encoding="utf-8",
        )

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(message="Root reference index written."),
                }
            )
        )


class DiscoverTranslateDocumentFragmentsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, DiscoverTranslateDocumentFragmentsTaskSpec):
            raise TypeError(
                "fragment discovery handler requires a "
                "DiscoverTranslateDocumentFragmentsTaskSpec"
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

        profile = config.llm.translator.get(spec.profile_name)
        if profile is None:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="Translator profile does not exist.",
                            error=spec.profile_name,
                        ),
                    }
                )
            )

        rendered_fragments = [render_markdown_fragment(fragment) for fragment in fragments]

        next_fragment_index = 0
        while next_fragment_index < len(fragments):
            chunk = _build_translation_chunk(
                fragments,
                rendered_fragments,
                next_fragment_index,
                profile,
            )
            task_key = make_translate_fragment_task_key(
                spec.relative_path,
                chunk.translation_input_digest,
                spec.profile_name,
                spec.profile_digest,
                spec.translation_hints_digest,
            )
            fragment_task_keys.append(task_key)

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=TranslateFragmentTaskSpec(
                            document_relative_path=spec.relative_path,
                            fragment_kind=chunk.first_fragment.fragment_kind,
                            heading_path=chunk.first_fragment.heading_path,
                            text=chunk.input_markdown,
                            input_markdown=chunk.input_markdown,
                            pre_context=chunk.pre_context,
                            post_context=chunk.post_context,
                            fragment_digest=chunk.fragment_digest,
                            profile_name=spec.profile_name,
                            profile_digest=spec.profile_digest,
                            translation_hints=spec.translation_hints,
                            translation_hints_digest=spec.translation_hints_digest,
                        ),
                    )
                )

            next_fragment_index = chunk.end_index + 1

        merge_task_key = make_merge_translated_fragments_task_key(
            spec.relative_path,
            spec.source_digest,
            spec.profile_name,
            spec.profile_digest,
            spec.plan_digest,
            spec.render_digest,
            spec.translation_hints_digest,
        )
        child_task_keys = [*fragment_task_keys, merge_task_key]

        if task_repository.get(merge_task_key) is None:
            discovered_records.append(
                TaskRecord(
                    task_key=merge_task_key,
                    spec=MergeTranslatedFragmentsTaskSpec(
                        document_relative_path=spec.relative_path,
                        source_digest=spec.source_digest,
                        fragment_task_keys=fragment_task_keys,
                        profile_name=spec.profile_name,
                        profile_digest=spec.profile_digest,
                        plan_digest=spec.plan_digest,
                        render_digest=spec.render_digest,
                        with_review=spec.with_review,
                        translation_hints_digest=spec.translation_hints_digest,
                        translated_document_header=spec.translated_document_header,
                        translated_document_footer=spec.translated_document_footer,
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
                "at least one translation task failed."
            )
        elif all_succeeded:
            status = TaskStatus.SUCCEEDED
            message = f"{len(fragment_task_keys)} fragments discovered and translated."
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
class TranslateFragmentTaskHandler:
    def __init__(self, llm_client: AbstractLlmClient | None = None) -> None:
        self._llm_client = llm_client
        self._owned_llm_clients: dict[str, AbstractLlmClient] = {}

    def close(self) -> None:
        for llm_client in self._owned_llm_clients.values():
            llm_client.close()
        self._owned_llm_clients.clear()

    def get_llm_timing_summary(self):
        llm_clients: list[AbstractLlmClient] = list(self._owned_llm_clients.values())
        if self._llm_client is not None:
            llm_clients.insert(0, self._llm_client)
        if not llm_clients:
            return None
        all_attempt_durations: list[float] = []
        for llm_client in llm_clients:
            all_attempt_durations.extend(llm_client.get_attempt_durations())
        if not all_attempt_durations:
            return None
        average_elapsed_seconds = sum(all_attempt_durations) / len(all_attempt_durations)
        variance_elapsed_seconds = pvariance(all_attempt_durations)
        return LlmCallTimingSummary(
            attempt_count=len(all_attempt_durations),
            average_elapsed_seconds=average_elapsed_seconds,
            variance_elapsed_seconds=variance_elapsed_seconds,
        )

    def _get_llm_client(self, config: WorkspaceConfig, profile_name: str) -> AbstractLlmClient:
        if self._llm_client is not None:
            return self._llm_client
        profile = config.llm.translator.get(profile_name)
        if profile is None:
            raise KeyError(f"Unknown translator profile: {profile_name}")
        if profile.api not in self._owned_llm_clients:
            self._owned_llm_clients[profile.api] = build_llm_client(profile.api)
        return self._owned_llm_clients[profile.api]

    def handle(self, record: TaskRecord, config: WorkspaceConfig) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, TranslateFragmentTaskSpec):
            raise TypeError("fragment translator requires a TranslateFragmentTaskSpec")

        fragment = MarkdownFragment(
            fragment_kind=spec.fragment_kind,
            heading_path=spec.heading_path,
            text=spec.text,
            length=len(spec.text),
        )
        fragment_markdown = spec.input_markdown or render_markdown_fragment(fragment)

        try:
            llm_client = self._get_llm_client(config, spec.profile_name)
            translated_fragment = llm_client.translate_fragment(
                config=config,
                profile_name=spec.profile_name,
                parameters={
                    "input_fragment": fragment_markdown,
                    "pre_context": spec.pre_context,
                    "post_context": spec.post_context,
                    "translation_hints": spec.translation_hints,
                },
            )
        except UnsupportedLlmProviderError as exc:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="LLM translation configuration failed.",
                            error=str(exc),
                            error_category="configuration",
                        ),
                    }
                )
            )
        except httpx.TimeoutException as exc:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="LLM translation timed out.",
                            error=str(exc),
                            error_category="timeout",
                        ),
                    }
                )
            )
        except httpx.HTTPStatusError as exc:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message=(
                                "LLM translation failed with an HTTP status error."
                            ),
                            error=str(exc),
                            error_category="http_status",
                            http_status_code=exc.response.status_code,
                        ),
                    }
                )
            )
        except httpx.RequestError as exc:
            return TaskHandlerResult(
                updated_record=record.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "outcome": TaskOutcome(
                            message="LLM translation request failed.",
                            error=str(exc),
                            error_category="request_error",
                        ),
                    }
                )
            )

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(
                        message="Fragment translated.",
                        result=TranslatedFragmentResult(
                            translated_text=translated_fragment,
                            length=len(translated_fragment),
                        ),
                    ),
                }
            )
        )


class MergeTranslatedFragmentsTaskHandler:
    def handle(
        self,
        record: TaskRecord,
        config: WorkspaceConfig,
        task_repository: JsonTaskRepository,
    ) -> TaskHandlerResult:
        spec = record.spec
        if not isinstance(spec, MergeTranslatedFragmentsTaskSpec):
            raise TypeError(
                "translated fragment merge handler requires a "
                "MergeTranslatedFragmentsTaskSpec"
            )

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

        if any(
            fragment_record is not None and fragment_record.status == TaskStatus.FAILED
            for fragment_record in fragment_records
        ):
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

        translated_fragments: list[str] = []
        source_fragments: list[str] = []
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

            translated_fragments.append(fragment_record.outcome.result.translated_text)
            source_fragments.append(fragment_record.spec.input_markdown or fragment_record.spec.text)

        destination_path = config.output_dir / spec.document_relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            render_translated_document(
                translated_fragments,
                header=spec.translated_document_header,
                footer=spec.translated_document_footer,
            ),
            encoding="utf-8",
        )

        if spec.with_review:
            review_path = config.output_dir / build_translation_review_path(spec.document_relative_path)
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(
                render_chunk_review_document(
                    source_path=spec.document_relative_path,
                    source_fragments=source_fragments,
                    translated_fragments=translated_fragments,
                    translated_first=config.translation_review.translated_first,
                ),
                encoding="utf-8",
            )

        return TaskHandlerResult(
            updated_record=record.model_copy(
                update={
                    "status": TaskStatus.SUCCEEDED,
                    "outcome": TaskOutcome(message="Translated document written."),
                }
            )
        )


def _build_source_digest(path: Path) -> str:
    digest = sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _build_checked_at_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_reference_index_entries(output_dir: Path) -> dict[str, ReferenceUrlIndexEntry]:
    sidecar = load_reference_index_sidecar(output_dir / build_root_reference_index_yaml_path())
    return {entry.url: entry for entry in sidecar.urls}


def _build_reference_url_occurrences(
    source_root: Path,
    relative_paths: list[Path],
) -> dict[str, list[ReferenceUrlOccurrence]]:
    references_by_url: dict[str, list[ReferenceUrlOccurrence]] = {}

    for relative_path in relative_paths:
        references = extract_markdown_references(source_root / relative_path)
        for reference in references:
            if not is_public_reference_url(reference.url):
                continue
            references_by_url.setdefault(reference.url, []).append(
                ReferenceUrlOccurrence(
                    document_path=relative_path.as_posix(),
                    heading_path=list(reference.heading_path),
                    label=reference.label,
                )
            )

    return references_by_url


def _merge_reference_index_sidecar(
    existing_sidecar: ReferenceIndexSidecar,
    reference_occurrences: dict[str, list[ReferenceUrlOccurrence]],
    url_check_results: dict[str, tuple[ReferenceUrlCheckResult | None, str | None, int | None]],
) -> ReferenceIndexSidecar:
    existing_entries = {entry.url: entry for entry in existing_sidecar.urls}
    merged_entries: list[ReferenceUrlIndexEntry] = []

    for url in sorted(set(existing_entries) | set(reference_occurrences)):
        existing_entry = existing_entries.get(url)
        occurrences = reference_occurrences.get(url, [])
        updated_entry = ReferenceUrlIndexEntry(url=url)
        if existing_entry is not None:
            updated_entry = existing_entry.model_copy(deep=True)

        updated_entry.references = list(occurrences)
        updated_entry.unused = not bool(occurrences)

        if url in url_check_results:
            result, error_category, http_status_code = url_check_results[url]
            updated_entry.error_category = error_category
            updated_entry.http_status_code = http_status_code
            if result is not None:
                if result.doi.strip() and not updated_entry.doi.strip():
                    updated_entry.doi = result.doi.strip()
                updated_entry.last_checked_at = result.checked_at
                updated_entry.redirect_location = result.redirect_location
                updated_entry.final_url = result.final_url
                updated_entry.content_type = result.content_type
                updated_entry.filename = result.filename
                updated_entry.reason_phrase = result.reason_phrase
                updated_entry.html_title = result.html_title
                updated_entry.html_excerpt = result.html_excerpt
                updated_entry.pdf_title = result.pdf_title
                updated_entry.pdf_author = result.pdf_author
                updated_entry.pdf_subject = result.pdf_subject
                updated_entry.pdf_preview_status = result.pdf_preview_status
                updated_entry.pdf_preview_max_bytes = result.pdf_preview_max_bytes
                updated_entry.pdf_excerpt = result.pdf_excerpt

        merged_entries.append(updated_entry)

    return ReferenceIndexSidecar(version=1, urls=merged_entries)


_HTML_PREVIEW_BYTE_LIMIT = 64 * 1024
_HTML_PREVIEW_TEXT_WIDTH = 100
def _extract_html_preview(
    response: httpx.Response,
    *,
    preview_max_text_chars: int,
    preview_max_lines: int,
) -> tuple[str | None, str | None, str]:
    content_type = (response.headers.get("content-type") or "").lower()
    if "html" not in content_type:
        return None, None, ""

    payload = _read_limited_response_bytes(response, _HTML_PREVIEW_BYTE_LIMIT)
    if not payload:
        return None, None, ""

    encoding = response.encoding or "utf-8"
    html = payload.decode(encoding, errors="ignore")
    title = _extract_html_title(html, str(response.url))
    excerpt = _extract_html_excerpt(
        html,
        str(response.url),
        preview_max_text_chars=preview_max_text_chars,
        preview_max_lines=preview_max_lines,
    )
    doi = _extract_doi_from_html(html, str(response.url), excerpt)
    return title, excerpt, doi


def _response_looks_like_pdf(response: httpx.Response, request_url: str) -> bool:
    content_type = (response.headers.get("content-type") or "").lower()
    if "application/pdf" in content_type:
        return True
    if content_type and "html" in content_type:
        return False

    resolved_filename = (_resolve_reference_url_filename(request_url, response) or "").lower()
    if resolved_filename.endswith(".pdf"):
        return True

    normalized_url = str(response.url).split("?", 1)[0].split("#", 1)[0].lower()
    return normalized_url.endswith(".pdf")


def _extract_pdf_preview(
    client: httpx.Client,
    url: str,
    max_pdf_bytes: int,
    *,
    preview_max_text_chars: int,
    preview_max_lines: int,
) -> tuple[str | None, str | None, str | None, str | None, int | None, str | None]:
    try:
        with client.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=20.0,
            headers={"Accept": "application/pdf,*/*"},
        ) as response:
            if response.is_error or not _response_looks_like_pdf(response, url):
                return None, None, None, None, None, None
            size_hint = _extract_response_size_hint(response)
            if size_hint is not None and size_hint > max_pdf_bytes:
                return None, None, None, "skipped_due_to_size_limit", max_pdf_bytes, None
            payload, truncated = _read_limited_response_bytes_with_overflow(response, max_pdf_bytes)
    except httpx.RequestError:
        return None, None, None, None, None, None

    if not payload:
        return None, None, None, None, None, None

    if truncated:
        return None, None, None, "skipped_due_to_size_limit", max_pdf_bytes, None

    pdf_title, pdf_author, pdf_subject, pdf_excerpt = _extract_pdf_preview_from_bytes(
        payload,
        preview_max_text_chars=preview_max_text_chars,
        preview_max_lines=preview_max_lines,
    )
    return pdf_title, pdf_author, pdf_subject, None, None, pdf_excerpt


def _extract_pdf_preview_from_bytes(
    payload: bytes,
    *,
    preview_max_text_chars: int,
    preview_max_lines: int,
) -> tuple[str | None, str | None, str | None, str | None]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(payload))
    except Exception:
        return None, None, None, None

    metadata = reader.metadata
    pdf_title = _normalize_pdf_metadata_value(getattr(metadata, "title", None))
    pdf_author = _normalize_pdf_metadata_value(getattr(metadata, "author", None))
    pdf_subject = _normalize_pdf_metadata_value(getattr(metadata, "subject", None))

    pdf_excerpt = None
    if reader.pages:
        try:
            pdf_excerpt = _format_pdf_excerpt(
                reader.pages[0].extract_text(),
                preview_max_text_chars=preview_max_text_chars,
                preview_max_lines=preview_max_lines,
            )
        except Exception:
            pdf_excerpt = None

    return pdf_title, pdf_author, pdf_subject, pdf_excerpt


def _read_limited_response_bytes(response: httpx.Response, limit: int) -> bytes:
    payload, _ = _read_limited_response_bytes_with_overflow(response, limit)
    return payload


def _read_limited_response_bytes_with_overflow(
    response: httpx.Response,
    limit: int,
) -> tuple[bytes, bool]:
    buffer = bytearray()
    truncated = False

    for chunk in response.iter_bytes():
        if not chunk:
            continue
        remaining = limit - len(buffer)
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            buffer.extend(chunk[:remaining])
            truncated = True
            break
        buffer.extend(chunk)
        if len(buffer) >= limit:
            continue

    return bytes(buffer), truncated


def _extract_response_size_hint(response: httpx.Response) -> int | None:
    content_range = response.headers.get("content-range")
    if content_range:
        match = re.match(r"^bytes\s+\d+-\d+/(?P<total>\d+|\*)$", content_range.strip())
        if match is not None and match.group("total") != "*":
            return int(match.group("total"))

    content_length = response.headers.get("content-length")
    if content_length is None:
        return None
    try:
        return int(content_length)
    except ValueError:
        return None


def _format_preview_excerpt(
    text: str,
    *,
    preview_max_text_chars: int,
    preview_max_lines: int,
) -> str | None:
    normalized = " ".join(text.split())
    if not normalized:
        return None

    clipped = normalized[:preview_max_text_chars].strip()
    wrapped = textwrap.wrap(clipped, width=_HTML_PREVIEW_TEXT_WIDTH)
    if not wrapped:
        return None
    return "\n".join(wrapped[:preview_max_lines])


def _format_pdf_excerpt(
    text: str | None,
    *,
    preview_max_text_chars: int,
    preview_max_lines: int,
) -> str | None:
    if text is None:
        return None
    return _format_preview_excerpt(
        text,
        preview_max_text_chars=preview_max_text_chars,
        preview_max_lines=preview_max_lines,
    )


def _extract_html_excerpt(
    html: str,
    url: str,
    *,
    preview_max_text_chars: int,
    preview_max_lines: int,
) -> str | None:
    extracted_text = extract(
        html,
        url=url,
        output_format="txt",
        include_comments=False,
        include_tables=False,
        fast=True,
    )
    if extracted_text is None:
        return None
    return _format_preview_excerpt(
        extracted_text,
        preview_max_text_chars=preview_max_text_chars,
        preview_max_lines=preview_max_lines,
    )


def _extract_html_title(html: str, url: str) -> str | None:
    fallback_title = _extract_html_title_fallback(html)
    extraction = bare_extraction(
        html,
        url=url,
        output_format="python",
        include_comments=False,
        include_tables=False,
        with_metadata=True,
    )
    if fallback_title:
        return fallback_title

    if extraction is not None and hasattr(extraction, "as_dict"):
        extraction = extraction.as_dict()

    if isinstance(extraction, dict):
        extracted_title = extraction.get("title")
        if isinstance(extracted_title, str):
            normalized = " ".join(extracted_title.split()).strip()
            if normalized:
                return normalized

    return None


def _extract_html_title_fallback(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return None
    normalized = " ".join(match.group(1).split()).strip()
    return normalized or None


def _normalize_pdf_metadata_value(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized or None


def _extract_redirect_location(response: httpx.Response) -> str | None:
    response_with_location: httpx.Response | None = None
    if 300 <= response.status_code < 400 and response.headers.get("location"):
        response_with_location = response
    elif response.history:
        for previous_response in reversed(response.history):
            if previous_response.headers.get("location"):
                response_with_location = previous_response
                break

    if response_with_location is None:
        return None

    location = response_with_location.headers.get("location")
    if location is None:
        return None

    normalized = location.strip()
    if not normalized:
        return None

    return urljoin(str(response_with_location.url), normalized)


_DOI_URL_PATTERN = re.compile(
    r"^(?:https?://)?(?:dx\.)?doi\.org/(?P<doi>10\.\d{4,9}/.+)$",
    flags=re.IGNORECASE,
)
_DOI_PATTERN = re.compile(
    r"(?P<doi>10\.\d{4,9}/[-._;()/:A-Za-z0-9]+[-_()/:A-Za-z0-9])",
    flags=re.IGNORECASE,
)
_DOI_META_TAG_PATTERN = re.compile(
    r"<meta\b(?P<attrs>[^>]+?)>",
    flags=re.IGNORECASE | re.DOTALL,
)
_HTML_ATTRIBUTE_PATTERN = re.compile(
    r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    flags=re.DOTALL,
)
_DOI_META_FIELDS = {
    "citation_doi",
    "dc.identifier",
    "dc.identifier.doi",
    "dc.source",
    "doi",
    "prism.doi",
}


def _extract_doi_from_candidates(*candidates: str | None) -> str:
    for candidate in candidates:
        normalized = (candidate or "").strip()
        if normalized:
            return normalized
    return ""


def _extract_doi_from_html(html: str, url: str, excerpt: str | None) -> str:
    return _extract_doi_from_candidates(
        _extract_doi_from_html_meta(html),
        _extract_doi_from_reference_url(url),
        _extract_doi_from_text(html),
        _extract_doi_from_text(excerpt),
    )


def _extract_doi_from_html_meta(html: str) -> str:
    for match in _DOI_META_TAG_PATTERN.finditer(html):
        attrs = {
            key.lower(): value.strip()
            for key, _, value in _HTML_ATTRIBUTE_PATTERN.findall(match.group("attrs"))
        }
        meta_name = (attrs.get("name") or attrs.get("property") or "").strip().lower()
        if meta_name not in _DOI_META_FIELDS:
            continue
        normalized = _normalize_doi_candidate(attrs.get("content", ""))
        if normalized:
            return normalized
    return ""


def _extract_doi_from_text(text: str | None) -> str:
    if not text:
        return ""
    match = _DOI_PATTERN.search(text)
    if match is None:
        return ""
    return _normalize_doi_candidate(match.group("doi"))


def _normalize_doi_candidate(value: str | None) -> str:
    if not value:
        return ""

    normalized = value.strip()
    if not normalized:
        return ""

    normalized = re.sub(
        r"^(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = normalized.strip().strip("<>")
    normalized = normalized.rstrip(".,;:)]}>")

    match = _DOI_PATTERN.search(normalized)
    if match is None:
        return ""
    return match.group("doi")


def _extract_doi_from_reference_urls(*urls: str | None) -> str:
    for candidate in urls:
        normalized = _extract_doi_from_reference_url(candidate)
        if normalized:
            return normalized
    return ""


def _extract_doi_from_reference_url(url: str | None) -> str | None:
    if not url:
        return None

    trimmed = url.strip()
    if not trimmed:
        return None

    match = _DOI_URL_PATTERN.match(trimmed)
    if match is not None:
        doi = unquote(match.group("doi")).strip().rstrip("/")
        if doi:
            return doi

    url_without_query = trimmed.split("?", 1)[0].split("#", 1)[0]
    decoded_url = unquote(url_without_query)
    normalized = _extract_doi_from_text(decoded_url)
    return normalized or None


def _build_fragment_digest(fragment: MarkdownFragment) -> str:
    payload = "|".join(
        [fragment.fragment_kind, *fragment.heading_path, fragment.text]
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _build_rendered_fragment_digest(rendered_fragments: list[str]) -> str:
    digest = sha256("|".join(rendered_fragments).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _build_translation_input_digest(
    fragment: MarkdownFragment,
    pre_context: str,
    post_context: str,
) -> str:
    payload = "|".join(
        [fragment.fragment_kind, *fragment.heading_path, fragment.text, pre_context, post_context]
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _build_translation_input_digest_from_markdown(
    input_markdown: str,
    pre_context: str,
    post_context: str,
) -> str:
    payload = "|".join([input_markdown, pre_context, post_context])
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _build_translation_chunk(
    fragments: list[MarkdownFragment],
    rendered_fragments: list[str],
    start_index: int,
    profile: TranslatorProfileConfig,
) -> TranslationChunk:
    first_fragment = fragments[start_index]
    first_rendered_fragment = rendered_fragments[start_index]
    pre_context = _build_neighbor_context(
        fragments,
        start_index,
        direction="pre",
        max_bytes=profile.max_pre_context_bytes,
    )

    if (
        profile.max_total_text_bytes <= 0
        and profile.max_input_fragment_bytes <= 0
    ):
        post_context = _build_neighbor_context(
            fragments,
            start_index,
            direction="post",
            max_bytes=profile.max_post_context_bytes,
        )
        return TranslationChunk(
            start_index=start_index,
            end_index=start_index,
            input_markdown=first_rendered_fragment,
            pre_context=pre_context,
            post_context=post_context,
            fragment_digest=_build_fragment_digest(first_fragment),
            translation_input_digest=_build_translation_input_digest(
                first_fragment,
                pre_context,
                post_context,
            ),
            first_fragment=first_fragment,
        )

    selected_rendered_fragments = [first_rendered_fragment]
    chunk_size = len(first_rendered_fragment.encode("utf-8"))
    end_index = start_index
    input_budget = _compute_initial_input_budget(profile, pre_context)

    while end_index + 1 < len(fragments):
        next_rendered_fragment = rendered_fragments[end_index + 1]
        candidate_size = chunk_size + len("\n\n".encode("utf-8")) + len(
            next_rendered_fragment.encode("utf-8")
        )
        if input_budget is not None and candidate_size > input_budget:
            break
        end_index += 1
        selected_rendered_fragments.append(next_rendered_fragment)
        chunk_size = candidate_size

    while True:
        post_context = _build_neighbor_context(
            fragments,
            end_index,
            direction="post",
            max_bytes=profile.max_post_context_bytes,
        )
        if end_index + 1 >= len(fragments):
            break
        if not _post_context_reaches_document_end(
            fragments,
            end_index,
            profile.max_post_context_bytes,
        ):
            break

        phase_two_budget = _compute_phase_two_input_budget(profile, pre_context)
        next_rendered_fragment = rendered_fragments[end_index + 1]
        candidate_size = chunk_size + len("\n\n".encode("utf-8")) + len(
            next_rendered_fragment.encode("utf-8")
        )
        if phase_two_budget is not None and candidate_size > phase_two_budget:
            break

        end_index += 1
        selected_rendered_fragments.append(next_rendered_fragment)
        chunk_size = candidate_size

    input_markdown = "\n\n".join(selected_rendered_fragments)
    post_context = _build_neighbor_context(
        fragments,
        end_index,
        direction="post",
        max_bytes=profile.max_post_context_bytes,
    )
    return TranslationChunk(
        start_index=start_index,
        end_index=end_index,
        input_markdown=input_markdown,
        pre_context=pre_context,
        post_context=post_context,
        fragment_digest=_build_rendered_fragment_digest(selected_rendered_fragments),
        translation_input_digest=_build_translation_input_digest_from_markdown(
            input_markdown,
            pre_context,
            post_context,
        ),
        first_fragment=first_fragment,
    )


def _compute_initial_input_budget(
    profile: TranslatorProfileConfig,
    pre_context: str,
) -> int | None:
    total_limit = profile.max_total_text_bytes if profile.max_total_text_bytes > 0 else None
    hard_limit = (
        profile.max_input_fragment_bytes if profile.max_input_fragment_bytes > 0 else None
    )

    budget = total_limit
    if total_limit is not None:
        budget = max(
            total_limit
            - profile.max_pre_context_bytes
            - profile.max_post_context_bytes,
            0,
        )
        budget += max(
            profile.max_pre_context_bytes - len(pre_context.encode("utf-8")),
            0,
        )

    if hard_limit is not None:
        if budget is None:
            return hard_limit
        return min(budget, hard_limit)
    return budget


def _compute_phase_two_input_budget(
    profile: TranslatorProfileConfig,
    pre_context: str,
) -> int | None:
    total_limit = profile.max_total_text_bytes if profile.max_total_text_bytes > 0 else None
    hard_limit = (
        profile.max_input_fragment_bytes if profile.max_input_fragment_bytes > 0 else None
    )

    budget = total_limit
    if total_limit is not None:
        budget = max(total_limit - len(pre_context.encode("utf-8")), 0)

    if hard_limit is not None:
        if budget is None:
            return hard_limit
        return min(budget, hard_limit)
    return budget


def _post_context_reaches_document_end(
    fragments: list[MarkdownFragment],
    fragment_index: int,
    max_bytes: int,
) -> bool:
    if max_bytes <= 0:
        return fragment_index >= len(fragments) - 1

    current_size = 0
    separator_size = len("\n\n".encode("utf-8"))
    last_eligible_index = fragment_index

    for neighbor_index in range(fragment_index + 1, len(fragments)):
        neighbor_fragment = fragments[neighbor_index]
        if not _include_fragment_in_neighbor_context(neighbor_fragment):
            continue

        rendered_neighbor = render_markdown_fragment(neighbor_fragment)
        neighbor_size = len(rendered_neighbor.encode("utf-8"))
        additional_size = neighbor_size
        if last_eligible_index != fragment_index:
            additional_size += separator_size

        if current_size + additional_size > max_bytes:
            return False

        current_size += additional_size
        last_eligible_index = neighbor_index

    return True


def _build_neighbor_context(
    fragments: list[MarkdownFragment],
    fragment_index: int,
    direction: str,
    max_bytes: int,
) -> str:
    if max_bytes <= 0:
        return ""

    selected_fragments: list[str] = []
    current_size = 0
    separator_size = len("\n\n".encode("utf-8"))

    if direction == "pre":
        indices = range(fragment_index - 1, -1, -1)
    elif direction == "post":
        indices = range(fragment_index + 1, len(fragments))
    else:
        raise ValueError(f"Unsupported direction: {direction}")

    for neighbor_index in indices:
        neighbor_fragment = fragments[neighbor_index]
        if not _include_fragment_in_neighbor_context(neighbor_fragment):
            continue

        rendered_neighbor = render_markdown_fragment(neighbor_fragment)
        neighbor_size = len(rendered_neighbor.encode("utf-8"))
        additional_size = neighbor_size
        if selected_fragments:
            additional_size += separator_size

        if current_size + additional_size > max_bytes:
            break

        if direction == "pre":
            selected_fragments.insert(0, rendered_neighbor)
        else:
            selected_fragments.append(rendered_neighbor)
        current_size += additional_size

    return "\n\n".join(selected_fragments)


def _include_fragment_in_neighbor_context(fragment: MarkdownFragment) -> bool:
    return fragment.fragment_kind not in {"code_block", "mermaid"}


def _iter_markdown_documents(
    root_path: Path,
    config: WorkspaceConfig,
    workflow_kind: str,
    default_translation_profile_name: str | None = None,
) -> list[DocumentWorkflowSettings]:
    local_config_cache: dict[Path, LocalWorkflowConfig | None] = {}
    return [
        document
        for path in root_path.rglob("*")
        if path.is_file()
        and (
            workflow_kind == "translate_document_tree"
            or path.suffix.lower() == ".md"
        )
        and (
            document := _resolve_document_workflow_settings(
                path,
                config,
                workflow_kind,
                default_translation_profile_name,
                local_config_cache,
            )
        )
        is not None
    ]


def _iter_resource_files(root_path: Path, config: WorkspaceConfig) -> list[Path]:
    local_config_cache: dict[Path, LocalWorkflowConfig | None] = {}
    return [
        path
        for path in root_path.rglob("*")
        if path.is_file()
        and _is_selected_resource_file(path.relative_to(config.input_dir), config)
        and _is_copy_resource_allowed(path, config.input_dir, local_config_cache)
    ]


def _resolve_document_workflow_settings(
    source_path: Path,
    config: WorkspaceConfig,
    workflow_kind: str,
    default_translation_profile_name: str | None,
    local_config_cache: dict[Path, LocalWorkflowConfig | None],
) -> DocumentWorkflowSettings | None:
    relative_path = source_path.relative_to(config.input_dir)
    if workflow_kind == "reference_index_tree":
        if not _is_selected_reference_document(relative_path, config):
            return None
    elif workflow_kind == "translate_document_tree":
        if not _is_selected_translation_document(relative_path, config):
            return None
    else:
        raise ValueError(f"Unsupported workflow kind: {workflow_kind}")

    excluded = False
    translation_profile_name = default_translation_profile_name
    translation_hints_parts: list[str] = []
    translated_document_header: str | None = None
    translated_document_footer: str | None = None

    for directory, local_config in _iter_applicable_local_workflow_configs(
        source_path,
        config.input_dir,
        local_config_cache,
    ):
        relative_to_directory = source_path.relative_to(directory)
        if workflow_kind == "reference_index_tree":
            for rule in local_config.reference_index.rules:
                if _path_matches_rule(relative_to_directory, rule.match) and rule.exclude:
                    excluded = True
        elif workflow_kind == "translate_document_tree":
            for rule in local_config.translation.rules:
                if not _path_matches_rule(relative_to_directory, rule.match):
                    continue
                if rule.exclude:
                    excluded = True
                if rule.profile is not None:
                    translation_profile_name = rule.profile
                if rule.hints is not None:
                    translation_hints_parts.append(rule.hints)
                if rule.translated_document_header is not None:
                    translated_document_header = rule.translated_document_header
                if rule.translated_document_footer is not None:
                    translated_document_footer = rule.translated_document_footer
        else:
            raise ValueError(f"Unsupported workflow kind: {workflow_kind}")

    if excluded:
        return None

    return DocumentWorkflowSettings(
        source_path=source_path,
        relative_path=relative_path,
        translation_profile_name=translation_profile_name,
        translation_hints="\n\n".join(part for part in translation_hints_parts if part),
        translated_document_header=translated_document_header,
        translated_document_footer=translated_document_footer,
    )


def _iter_applicable_local_workflow_configs(
    source_path: Path,
    input_dir: Path,
    local_config_cache: dict[Path, LocalWorkflowConfig | None],
) -> list[tuple[Path, LocalWorkflowConfig]]:
    directories: list[Path] = []
    current_directory = source_path.parent
    while True:
        directories.append(current_directory)
        if current_directory == input_dir:
            break
        current_directory = current_directory.parent

    applicable_configs: list[tuple[Path, LocalWorkflowConfig]] = []
    for directory in reversed(directories):
        config_path = directory / LOCAL_WORKFLOW_CONFIG_NAME
        if config_path not in local_config_cache:
            local_config_cache[config_path] = (
                load_local_workflow_config(config_path) if config_path.exists() else None
            )
        local_config = local_config_cache[config_path]
        if local_config is None:
            continue
        applicable_configs.append((directory, local_config))

    return applicable_configs


def _build_optional_text_digest(text: str) -> str | None:
    if not text:
        return None
    return f"sha256:{sha256(text.encode('utf-8')).hexdigest()}"


def _is_selected_markdown_document(relative_path: Path, config: WorkspaceConfig) -> bool:
    return _is_selected_path(relative_path, config.file_selection)


def _is_selected_reference_document(relative_path: Path, config: WorkspaceConfig) -> bool:
    return (
        relative_path.suffix.lower() == ".md"
        and not _is_generated_reference_report_path(relative_path)
        and _is_selected_markdown_document(relative_path, config)
    )


def _is_selected_translation_document(relative_path: Path, config: WorkspaceConfig) -> bool:
    if relative_path.suffix.lower() == ".md":
        return _is_selected_markdown_document(relative_path, config)
    return _is_explicitly_included_path(relative_path, config.file_selection)


def _is_selected_resource_file(relative_path: Path, config: WorkspaceConfig) -> bool:
    return _is_selected_path(relative_path, config.resource_selection)


def _is_generated_reference_report_path(relative_path: Path) -> bool:
    return relative_path.name.endswith(".references.md") or relative_path == build_root_reference_index_path()


def _is_copy_resource_allowed(
    source_path: Path,
    input_dir: Path,
    local_config_cache: dict[Path, LocalWorkflowConfig | None],
) -> bool:
    for directory, local_config in _iter_applicable_local_workflow_configs(
        source_path,
        input_dir,
        local_config_cache,
    ):
        relative_to_directory = source_path.relative_to(directory)
        for rule in local_config.resource_copy.rules:
            if _path_matches_rule(relative_to_directory, rule.match) and rule.exclude:
                return False
    return True


def _resolve_reference_url_filename(url: str, response: httpx.Response | None) -> str | None:
    if response is not None:
        content_disposition = response.headers.get("content-disposition")
        filename = _parse_content_disposition_filename(content_disposition)
        if filename:
            return filename

        final_name = _basename_from_url(str(response.url))
        if final_name:
            return final_name

    return _basename_from_url(url)


def _parse_content_disposition_filename(header_value: str | None) -> str | None:
    if not header_value:
        return None

    for part in header_value.split(";"):
        candidate = part.strip()
        if candidate.lower().startswith("filename*="):
            _, value = candidate.split("=", 1)
            value = value.strip().strip('"')
            if "''" in value:
                _, encoded_value = value.split("''", 1)
                return unquote(encoded_value)
            return unquote(value)
        if candidate.lower().startswith("filename="):
            _, value = candidate.split("=", 1)
            return value.strip().strip('"') or None

    return None


def _basename_from_url(url: str) -> str | None:
    path = urlsplit(url).path
    if not path:
        return None
    basename = PurePosixPath(unquote(path)).name
    return basename or None


def _is_selected_path(relative_path: Path, selection) -> bool:
    selected = selection.default_action == "include"

    for rule in selection.rules:
        if _path_matches_rule(relative_path, rule.match):
            selected = rule.action == "include"

    return selected


def _is_explicitly_included_path(relative_path: Path, selection) -> bool:
    selected = selection.default_action == "include"
    explicitly_included = False

    for rule in selection.rules:
        if _path_matches_rule(relative_path, rule.match):
            selected = rule.action == "include"
            explicitly_included = rule.action == "include"

    return selected and explicitly_included


def _path_matches_rule(relative_path: Path, pattern: str) -> bool:
    relative_posix_path = PurePosixPath(relative_path.as_posix())
    candidate_patterns = [pattern]
    if candidate_patterns[-1].startswith("**/"):
        candidate_patterns.append(candidate_patterns[-1][3:])
    while "/**/" in candidate_patterns[-1]:
        candidate_patterns.append(candidate_patterns[-1].replace("/**/", "/", 1))

    return any(relative_posix_path.match(candidate) for candidate in candidate_patterns)