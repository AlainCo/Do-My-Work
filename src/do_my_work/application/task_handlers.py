from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path, PurePosixPath

import httpx

from do_my_work.application.task_keys import (
    make_discover_translate_document_fragments_task_key,
    make_index_markdown_references_task_key,
    make_merge_reference_indexes_task_key,
    make_merge_translated_fragments_task_key,
    make_translation_plan_digest,
    make_translate_fragment_task_key,
    make_translated_document_render_digest,
    make_translator_profile_digest,
)
from do_my_work.domain.models import (
    DiscoverReferenceDocumentsTaskSpec,
    DiscoverTranslateDocumentFragmentsTaskSpec,
    DiscoverTranslateDocumentsTaskSpec,
    IndexMarkdownReferencesTaskSpec,
    MarkdownFragment,
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
from do_my_work.infrastructure.json_workflow_store import JsonTaskRepository
from do_my_work.infrastructure.markdown_fragment_report import (
    extract_markdown_fragments,
    render_markdown_fragment,
    render_translated_document,
)
from do_my_work.infrastructure.markdown_reference_report import (
    build_reference_report_relative_path,
    build_root_reference_index_path,
    render_markdown_reference_report,
    render_tree_markdown_reference_report,
)
from do_my_work.infrastructure.ollama_client import OllamaChatClient


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

        for source_path in sorted(_iter_markdown_documents(root_path, config)):
            relative_path = source_path.relative_to(config.input_dir)
            document_relative_paths.append(relative_path)
            source_digest = _build_source_digest(source_path)
            task_key = make_index_markdown_references_task_key(relative_path, source_digest)
            child_task_keys.append(task_key)

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

        merge_task_key = make_merge_reference_indexes_task_key(spec.root, document_relative_paths)
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
                    ),
                    child_task_keys=[
                        make_index_markdown_references_task_key(
                            relative_path,
                            _build_source_digest(config.input_dir / relative_path),
                        )
                        for relative_path in document_relative_paths
                    ],
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

        profile_digest = make_translator_profile_digest(profile)
        plan_digest = make_translation_plan_digest(profile)
        render_digest = make_translated_document_render_digest(profile)
        discovered_records: list[TaskRecord] = []
        child_task_keys: list[str] = []

        for source_path in sorted(_iter_markdown_documents(root_path, config)):
            relative_path = source_path.relative_to(config.input_dir)
            source_digest = _build_source_digest(source_path)
            task_key = make_discover_translate_document_fragments_task_key(
                relative_path,
                source_digest,
                spec.profile_name,
                profile_digest,
                plan_digest,
                render_digest,
            )
            child_task_keys.append(task_key)

            if task_repository.get(task_key) is None:
                discovered_records.append(
                    TaskRecord(
                        task_key=task_key,
                        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
                            relative_path=relative_path,
                            source_digest=source_digest,
                            profile_name=spec.profile_name,
                            profile_digest=profile_digest,
                            plan_digest=plan_digest,
                            render_digest=render_digest,
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

        destination_path = config.output_dir / build_root_reference_index_path()
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            render_tree_markdown_reference_report(
                config.input_dir,
                spec.document_relative_paths,
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
                        translated_document_header=profile.translated_document_header,
                        translated_document_footer=profile.translated_document_footer,
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
    def __init__(self, llm_client: OllamaChatClient | None = None) -> None:
        self._llm_client = llm_client
        self._owned_llm_client: OllamaChatClient | None = None

    def close(self) -> None:
        if self._owned_llm_client is None:
            return
        self._owned_llm_client.close()
        self._owned_llm_client = None

    def get_llm_timing_summary(self):
        llm_client = self._llm_client or self._owned_llm_client
        if llm_client is None:
            return None
        return llm_client.get_timing_summary()

    def _get_llm_client(self) -> OllamaChatClient:
        if self._llm_client is not None:
            return self._llm_client
        if self._owned_llm_client is None:
            self._owned_llm_client = OllamaChatClient()
        return self._owned_llm_client

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

        llm_client = self._get_llm_client()
        try:
            translated_fragment = llm_client.translate_fragment(
                config=config,
                profile_name=spec.profile_name,
                parameters={
                    "input_fragment": fragment_markdown,
                    "pre_context": spec.pre_context,
                    "post_context": spec.post_context,
                },
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


def _iter_markdown_documents(root_path: Path, config: WorkspaceConfig) -> list[Path]:
    return [
        path
        for path in root_path.rglob("*")
        if path.is_file()
        and path.suffix.lower() == ".md"
        and _is_selected_markdown_document(path.relative_to(config.input_dir), config)
    ]


def _is_selected_markdown_document(relative_path: Path, config: WorkspaceConfig) -> bool:
    selection = config.file_selection
    selected = selection.default_action == "include"

    for rule in selection.rules:
        if _path_matches_rule(relative_path, rule.match):
            selected = rule.action == "include"

    return selected


def _path_matches_rule(relative_path: Path, pattern: str) -> bool:
    relative_posix_path = PurePosixPath(relative_path.as_posix())
    candidate_patterns = [pattern]
    while "/**/" in candidate_patterns[-1]:
        candidate_patterns.append(candidate_patterns[-1].replace("/**/", "/", 1))

    return any(relative_posix_path.match(candidate) for candidate in candidate_patterns)