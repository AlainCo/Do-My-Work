from pathlib import Path

import httpx

from do_my_work.application.task_handlers import (
    CopyFileTaskHandler,
    DiscoverDocumentFragmentsTaskHandler,
    DiscoverDocumentsTaskHandler,
    MergeFragmentResultsTaskHandler,
    MergeTranslatedFragmentsTaskHandler,
    TranslateFragmentTaskHandler,
)
from do_my_work.application.task_keys import (
    make_copy_task_key,
    make_discover_documents_task_key,
    make_merge_fragment_results_task_key,
    make_merge_translated_fragments_task_key,
)
from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverDocumentFragmentsTaskSpec,
    DiscoverDocumentsTaskSpec,
    LlmConfig,
    MergeFragmentResultsTaskSpec,
    MergeTranslatedFragmentsTaskSpec,
    ProcessedFragmentResult,
    ProcessFragmentTaskSpec,
    TaskOutcome,
    TaskRecord,
    TaskStatus,
    TranslateFragmentTaskSpec,
    TranslatorProfileConfig,
    WorkspaceConfig,
)
from do_my_work.infrastructure.json_workflow_store import JsonTaskRepository
from do_my_work.infrastructure.ollama_client import OllamaChatClient


def test_discover_documents_handler_fails_when_input_root_is_missing(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    record = TaskRecord(
        task_key=make_discover_documents_task_key(Path("missing")),
        spec=DiscoverDocumentsTaskSpec(root=Path("missing")),
    )

    result = DiscoverDocumentsTaskHandler().handle(
        record,
        config,
        JsonTaskRepository(config.data_dir / "tasks"),
    )

    assert result.new_records == []
    assert result.updated_record.status == TaskStatus.FAILED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.message == "Input root does not exist."
    assert result.updated_record.outcome.error == str(config.input_dir / "missing")


def test_copy_file_handler_fails_when_source_document_is_missing(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    relative_path = Path("nested/missing.md")
    record = TaskRecord(
        task_key=make_copy_task_key(relative_path, "sha256:missing"),
        spec=CopyFileTaskSpec(
            relative_path=relative_path,
            source_digest="sha256:missing",
        ),
    )

    result = CopyFileTaskHandler().handle(record, config)

    assert result.new_records == []
    assert result.updated_record.status == TaskStatus.FAILED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.message == "Source file does not exist."
    assert result.updated_record.outcome.error == str(config.input_dir / relative_path)


def test_discover_document_fragments_handler_creates_fragment_and_merge_tasks(
    tmp_path: Path,
) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    relative_path = Path("note.md")
    source_path = config.input_dir / relative_path
    source_path.write_text("# Intro\n\nAlpha beta.\n", encoding="utf-8")
    record = TaskRecord(
        task_key="task:discover_document_fragments:abc",
        spec=DiscoverDocumentFragmentsTaskSpec(
            relative_path=relative_path,
            source_digest="sha256:doc",
        ),
    )

    result = DiscoverDocumentFragmentsTaskHandler().handle(
        record,
        config,
        JsonTaskRepository(config.data_dir / "tasks"),
    )

    assert result.updated_record.status == TaskStatus.WAITING
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.message == "2 fragments discovered."
    assert [new_record.spec.kind for new_record in result.new_records] == [
        "process_fragment",
        "process_fragment",
        "merge_fragment_results",
    ]


def test_merge_fragment_results_handler_writes_report_from_fragment_task_results(
    tmp_path: Path,
) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    task_repository = JsonTaskRepository(config.data_dir / "tasks")

    fragment_task_keys = ["task:process_fragment:1", "task:process_fragment:2"]
    task_repository.save(
        TaskRecord(
            task_key=fragment_task_keys[0],
            spec=ProcessFragmentTaskSpec(
                document_relative_path=Path("note.md"),
                fragment_kind="heading",
                heading_path=["Intro"],
                text="Intro",
                fragment_digest="sha256:1",
            ),
            status=TaskStatus.SUCCEEDED,
            outcome=TaskOutcome(
                message="Fragment processed.",
                result=ProcessedFragmentResult(
                    rendered_text="- heading [Intro] -> 5",
                    length=5,
                ),
            ),
        )
    )
    task_repository.save(
        TaskRecord(
            task_key=fragment_task_keys[1],
            spec=ProcessFragmentTaskSpec(
                document_relative_path=Path("note.md"),
                fragment_kind="paragraph",
                heading_path=["Intro"],
                text="Alpha beta.",
                fragment_digest="sha256:2",
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
    )

    record = TaskRecord(
        task_key=make_merge_fragment_results_task_key(Path("note.md"), "sha256:doc"),
        spec=MergeFragmentResultsTaskSpec(
            document_relative_path=Path("note.md"),
            source_digest="sha256:doc",
            fragment_task_keys=fragment_task_keys,
            footer_text="Processed by workflow.",
        ),
    )

    result = MergeFragmentResultsTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert (config.output_dir / "note.summary.md").read_text(encoding="utf-8") == (
        "# Fragment Length Report\n\n"
        "Source: note.md\n\n"
        "- heading [Intro] -> 5\n"
        "- paragraph [Intro] -> 11\n\n"
        "Processed by workflow.\n"
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
    assert result.updated_record.outcome.result == ProcessedFragmentResult(
        rendered_text="# INTRO",
        length=7,
    )
    assert '"content":"===BEGIN SOURCE TEXT===\\n# Intro\\n===END SOURCE TEXT===\\n"' in str(
        captured_payload["payload"]
    )


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
                result=ProcessedFragmentResult(rendered_text="# INTRO", length=7),
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
                result=ProcessedFragmentResult(rendered_text="ALPHA BETA.", length=11),
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