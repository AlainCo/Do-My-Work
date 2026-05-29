from pathlib import Path

import httpx

from do_my_work.application.task_handlers import (
    IndexMarkdownReferencesTaskHandler,
    MergeReferenceIndexesTaskHandler,
    MergeTranslatedFragmentsTaskHandler,
    TranslateFragmentTaskHandler,
)
from do_my_work.application.task_keys import (
    make_index_markdown_references_task_key,
    make_merge_reference_indexes_task_key,
    make_merge_translated_fragments_task_key,
)
from do_my_work.domain.models import (
    IndexMarkdownReferencesTaskSpec,
    LlmConfig,
    MergeReferenceIndexesTaskSpec,
    MergeTranslatedFragmentsTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    TranslatedFragmentResult,
    TranslateFragmentTaskSpec,
    TranslatorProfileConfig,
    WorkspaceConfig,
)
from do_my_work.infrastructure.json_workflow_store import JsonTaskRepository
from do_my_work.infrastructure.ollama_client import OllamaChatClient


def test_index_markdown_references_handler_writes_reference_report(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    relative_path = Path("note.md")
    (config.input_dir / relative_path).write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    record = TaskRecord(
        task_key=make_index_markdown_references_task_key(relative_path, "sha256:doc"),
        spec=IndexMarkdownReferencesTaskSpec(
            relative_path=relative_path,
            source_digest="sha256:doc",
        ),
    )

    result = IndexMarkdownReferencesTaskHandler().handle(record, config)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert (config.output_dir / "note.references.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Index\n\n"
        "Source: note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )


def test_merge_reference_indexes_handler_writes_root_reference_index(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    (config.input_dir / "alpha.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    (config.input_dir / "nested").mkdir(parents=True)
    (config.input_dir / "nested" / "beta.md").write_text(
        "# Further Reading\n\nSee [Alice](https://example.org/alice).\n",
        encoding="utf-8",
    )

    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    alpha_task_key = make_index_markdown_references_task_key(Path("alpha.md"), "sha256:alpha")
    beta_task_key = make_index_markdown_references_task_key(Path("nested/beta.md"), "sha256:beta")
    task_repository.save(
        TaskRecord(
            task_key=alpha_task_key,
            spec=IndexMarkdownReferencesTaskSpec(
                relative_path=Path("alpha.md"),
                source_digest="sha256:alpha",
            ),
            status=TaskStatus.SUCCEEDED,
            outcome=TaskOutcome(message="Markdown reference report written."),
        )
    )
    task_repository.save(
        TaskRecord(
            task_key=beta_task_key,
            spec=IndexMarkdownReferencesTaskSpec(
                relative_path=Path("nested/beta.md"),
                source_digest="sha256:beta",
            ),
            status=TaskStatus.SUCCEEDED,
            outcome=TaskOutcome(message="Markdown reference report written."),
        )
    )

    record = TaskRecord(
        task_key=make_merge_reference_indexes_task_key(
            Path("."),
            [Path("alpha.md"), Path("nested/beta.md")],
        ),
        spec=MergeReferenceIndexesTaskSpec(
            root=Path("."),
            document_relative_paths=[Path("alpha.md"), Path("nested/beta.md")],
            reference_task_keys=[alpha_task_key, beta_task_key],
        ),
        child_task_keys=[alpha_task_key, beta_task_key],
    )

    result = MergeReferenceIndexesTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert (config.output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## nested/beta.md\n\n"
        "- [Alice](https://example.org/alice) [Further Reading]\n"
    )


def test_translate_fragment_handler_calls_llm_with_markdown_snippet(tmp_path: Path) -> None:
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload["payload"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "# INTRO"}},
        )

    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    temperature=0.0,
                    system_prompt="You are a professional translatoir from french to english.",
                    user_prompt=(
                        "===BEGIN SOURCE TEXT===\n"
                        "${inputfragment}\n"
                        "===END SOURCE TEXT===\n"
                    ),
                )
            }
        ),
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    llm_client = OllamaChatClient(http_client=http_client)
    record = TaskRecord(
        task_key="task:translate_fragment:abc",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="heading",
            heading_path=["Intro"],
            text="Intro",
            fragment_digest="sha256:frag",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = TranslateFragmentTaskHandler(llm_client=llm_client).handle(record, config)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.result == TranslatedFragmentResult(
        translated_text="# INTRO",
        length=7,
    )
    assert '"content":"===BEGIN SOURCE TEXT===\\n# Intro\\n===END SOURCE TEXT===\\n"' in str(
        captured_payload["payload"]
    )


def test_translate_fragment_handler_marks_timeout_as_failed(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("mock timeout while translating fragment", request=request)

    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    temperature=0.0,
                    system_prompt="You are a professional translator from french to english.",
                    user_prompt="${inputfragment}",
                )
            }
        ),
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    llm_client = OllamaChatClient(http_client=http_client)
    record = TaskRecord(
        task_key="task:translate_fragment:timeout",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Bonjour monde.",
            fragment_digest="sha256:frag-timeout",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = TranslateFragmentTaskHandler(llm_client=llm_client).handle(record, config)

    assert result.updated_record.status == TaskStatus.FAILED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.message == "LLM translation timed out."
    assert result.updated_record.outcome.error == "mock timeout while translating fragment"
    assert result.updated_record.outcome.error_category == "timeout"


def test_translate_fragment_handler_marks_http_status_error_as_failed(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request, json={"error": "service unavailable"})

    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    temperature=0.0,
                    system_prompt="You are a professional translator from french to english.",
                    user_prompt="${inputfragment}",
                )
            }
        ),
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    llm_client = OllamaChatClient(http_client=http_client)
    record = TaskRecord(
        task_key="task:translate_fragment:http-status",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Bonjour monde.",
            fragment_digest="sha256:frag-http-status",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = TranslateFragmentTaskHandler(llm_client=llm_client).handle(record, config)

    assert result.updated_record.status == TaskStatus.FAILED
    assert result.updated_record.outcome is not None
    assert (
        result.updated_record.outcome.message
        == "LLM translation failed with an HTTP status error."
    )
    assert "503 Service Unavailable" in result.updated_record.outcome.error
    assert result.updated_record.outcome.error_category == "http_status"


def test_translate_fragment_handler_marks_request_error_as_failed(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("mock connection failed", request=request)

    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    temperature=0.0,
                    system_prompt="You are a professional translator from french to english.",
                    user_prompt="${inputfragment}",
                )
            }
        ),
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    llm_client = OllamaChatClient(http_client=http_client)
    record = TaskRecord(
        task_key="task:translate_fragment:request-error",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("note.md"),
            fragment_kind="paragraph",
            heading_path=["Intro"],
            text="Bonjour monde.",
            fragment_digest="sha256:frag-request-error",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = TranslateFragmentTaskHandler(llm_client=llm_client).handle(record, config)

    assert result.updated_record.status == TaskStatus.FAILED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.message == "LLM translation request failed."
    assert result.updated_record.outcome.error == "mock connection failed"
    assert result.updated_record.outcome.error_category == "request_error"


def test_merge_translated_fragments_handler_writes_translated_document(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    fragment_task_keys = ["task:translate_fragment:1", "task:translate_fragment:2"]
    task_repository.save(
        TaskRecord(
            task_key=fragment_task_keys[0],
            spec=TranslateFragmentTaskSpec(
                document_relative_path=Path("note.md"),
                fragment_kind="heading",
                heading_path=["Intro"],
                text="Intro",
                fragment_digest="sha256:1",
                profile_name="technical",
                profile_digest="sha256:profile",
            ),
            status=TaskStatus.SUCCEEDED,
            outcome=TaskOutcome(
                message="Fragment translated.",
                result=TranslatedFragmentResult(translated_text="# INTRO", length=7),
            ),
        )
    )
    task_repository.save(
        TaskRecord(
            task_key=fragment_task_keys[1],
            spec=TranslateFragmentTaskSpec(
                document_relative_path=Path("note.md"),
                fragment_kind="paragraph",
                heading_path=["Intro"],
                text="Alpha beta.",
                fragment_digest="sha256:2",
                profile_name="technical",
                profile_digest="sha256:profile",
            ),
            status=TaskStatus.SUCCEEDED,
            outcome=TaskOutcome(
                message="Fragment translated.",
                result=TranslatedFragmentResult(translated_text="ALPHA BETA.", length=11),
            ),
        )
    )

    record = TaskRecord(
        task_key=make_merge_translated_fragments_task_key(
            Path("note.md"),
            "sha256:doc",
            "technical",
            "sha256:profile",
        ),
        spec=MergeTranslatedFragmentsTaskSpec(
            document_relative_path=Path("note.md"),
            source_digest="sha256:doc",
            fragment_task_keys=fragment_task_keys,
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = MergeTranslatedFragmentsTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert (config.output_dir / "note.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n"
    )