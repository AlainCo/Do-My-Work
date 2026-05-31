from pathlib import Path

import httpx
import pytest
import yaml

from do_my_work.application.task_handlers import (
    CheckReferenceUrlTaskHandler,
    DiscoverReferenceDocumentsTaskHandler,
    DiscoverTranslateDocumentFragmentsTaskHandler,
    IndexMarkdownReferencesTaskHandler,
    MergeReferenceIndexesTaskHandler,
    MergeTranslatedFragmentsTaskHandler,
    TranslateFragmentTaskHandler,
)
from do_my_work.application.task_keys import (
    make_check_reference_url_task_key,
    make_discover_reference_documents_task_key,
    make_index_markdown_references_task_key,
    make_merge_reference_indexes_task_key,
    make_merge_translated_fragments_task_key,
)
from do_my_work.domain.models import (
    CheckReferenceUrlTaskSpec,
    DiscoverReferenceDocumentsTaskSpec,
    DiscoverTranslateDocumentFragmentsTaskSpec,
    IndexMarkdownReferencesTaskSpec,
    LlmConfig,
    MergeReferenceIndexesTaskSpec,
    MergeTranslatedFragmentsTaskSpec,
    ReferenceUrlCheckResult,
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
        "- [Alice](https://example.org/alice) [Further Reading]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/alice\n\n"
        "References:\n"
        "- nested/beta.md [Further Reading] Alice\n\n"
        "### https://example.org/bob\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n"
    )


def test_check_reference_url_handler_records_http_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://example.org/files/report.pdf")
        return httpx.Response(
            200,
            headers={
                "content-type": "application/pdf",
                "content-disposition": 'attachment; filename="report.pdf"',
            },
            request=request,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    record = TaskRecord(
        task_key=make_check_reference_url_task_key("https://example.org/files/report.pdf"),
        spec=CheckReferenceUrlTaskSpec(url="https://example.org/files/report.pdf"),
    )

    result = CheckReferenceUrlTaskHandler(http_client=http_client).handle(
        record,
        WorkspaceConfig(),
    )

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.http_status_code == 200
    assert isinstance(result.updated_record.outcome.result, ReferenceUrlCheckResult)
    assert result.updated_record.outcome.result.url == "https://example.org/files/report.pdf"
    assert result.updated_record.outcome.result.checked_at is not None
    assert result.updated_record.outcome.result.doi == ""
    assert result.updated_record.outcome.result.final_url == "https://example.org/files/report.pdf"
    assert result.updated_record.outcome.result.content_type == "application/pdf"
    assert result.updated_record.outcome.result.filename == "report.pdf"
    assert result.updated_record.outcome.result.reason_phrase == "OK"


def test_check_reference_url_handler_extracts_doi_from_doi_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><head><title>Paper</title></head><body>Paper.</body></html>",
            request=request,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    record = TaskRecord(
        task_key=make_check_reference_url_task_key("https://doi.org/10.1000/example.paper"),
        spec=CheckReferenceUrlTaskSpec(url="https://doi.org/10.1000/example.paper"),
    )

    result = CheckReferenceUrlTaskHandler(http_client=http_client).handle(
        record,
        WorkspaceConfig(),
    )

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert result.updated_record.outcome is not None
    assert isinstance(result.updated_record.outcome.result, ReferenceUrlCheckResult)
    assert result.updated_record.outcome.result.doi == "10.1000/example.paper"


def test_check_reference_url_handler_extracts_html_title_and_excerpt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=(
                "<html><head><title>Example article</title></head>"
                "<body><h1>Ignored heading</h1><p>First sentence about the article preview. "
                "Second sentence adds a bit more detail for the plain text excerpt.</p>"
                "<script>window.ignore = true;</script></body></html>"
            ).encode("utf-8"),
            request=request,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    record = TaskRecord(
        task_key=make_check_reference_url_task_key("https://example.org/article"),
        spec=CheckReferenceUrlTaskSpec(url="https://example.org/article"),
    )

    result = CheckReferenceUrlTaskHandler(http_client=http_client).handle(
        record,
        WorkspaceConfig(),
    )

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert result.updated_record.outcome is not None
    assert isinstance(result.updated_record.outcome.result, ReferenceUrlCheckResult)
    assert result.updated_record.outcome.result.html_title == "Example article"
    assert result.updated_record.outcome.result.html_excerpt is not None
    assert "First sentence about the article preview." in result.updated_record.outcome.result.html_excerpt
    assert "window.ignore" not in result.updated_record.outcome.result.html_excerpt


def test_check_reference_url_handler_records_request_errors_without_failing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("certificate verify failed", request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    record = TaskRecord(
        task_key=make_check_reference_url_task_key("https://example.org/broken"),
        spec=CheckReferenceUrlTaskSpec(url="https://example.org/broken"),
    )

    result = CheckReferenceUrlTaskHandler(http_client=http_client).handle(
        record,
        WorkspaceConfig(),
    )

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.message == "URL check recorded a request error."
    assert result.updated_record.outcome.error_category == "request_error"
    assert result.updated_record.outcome.error == "certificate verify failed"


def test_check_reference_url_handler_creates_lax_tls_client_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    class FakeClient:
        def close(self) -> None:
            return None

    def fake_client(**kwargs):
        captured_kwargs.update(kwargs)
        return FakeClient()

    monkeypatch.setattr(httpx, "Client", fake_client)

    handler = CheckReferenceUrlTaskHandler()

    client = handler._get_http_client()

    assert isinstance(client, FakeClient)
    assert captured_kwargs == {"verify": False}


def test_merge_reference_indexes_handler_includes_http_error_url_checks_in_root_report(
    tmp_path: Path,
) -> None:
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

    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    alpha_task_key = make_index_markdown_references_task_key(Path("alpha.md"), "sha256:alpha")
    url_task_key = make_check_reference_url_task_key("https://example.org/bob")
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
            task_key=url_task_key,
            spec=CheckReferenceUrlTaskSpec(url="https://example.org/bob"),
            status=TaskStatus.SUCCEEDED,
            outcome=TaskOutcome(
                message="URL check recorded an HTTP error status.",
                error="Forbidden",
                error_category="http_status",
                http_status_code=403,
                result=ReferenceUrlCheckResult(
                    url="https://example.org/bob",
                    final_url="https://example.org/bob",
                    content_type="text/html",
                    filename="bob",
                    reason_phrase="Forbidden",
                ),
            ),
        )
    )

    record = TaskRecord(
        task_key=make_merge_reference_indexes_task_key(
            Path("."),
            [Path("alpha.md")],
            checked_urls=["https://example.org/bob"],
        ),
        spec=MergeReferenceIndexesTaskSpec(
            root=Path("."),
            document_relative_paths=[Path("alpha.md")],
            reference_task_keys=[alpha_task_key],
            url_check_task_keys=[url_task_key],
        ),
        child_task_keys=[alpha_task_key, url_task_key],
    )

    result = MergeReferenceIndexesTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert (config.output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/bob\n\n"
        "- Status: 403 Forbidden\n"
        "- Content-Type: text/html\n"
        "- Filename: bob\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n"
    )
    assert yaml.safe_load((config.output_dir / "references.index.yaml").read_text(encoding="utf-8")) == {
        "version": 1,
        "urls": [
            {
                "url": "https://example.org/bob",
                "skip_recheck": False,
                "unused": False,
                "doi": "",
                "error_category": "http_status",
                "http_status_code": 403,
                "final_url": "https://example.org/bob",
                "content_type": "text/html",
                "filename": "bob",
                "reason_phrase": "Forbidden",
                "references": [
                    {
                        "document_path": "alpha.md",
                        "heading_path": ["Sources"],
                        "label": "Bob",
                    }
                ],
            }
        ],
    }


def test_discover_reference_documents_ignores_relative_links_for_url_checks(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    (config.input_dir / "note.md").write_text(
        "# Sources\n\nSee [Local](./appendix.md).\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    record = TaskRecord(
        task_key=make_discover_reference_documents_task_key(Path("."), check_urls=True),
        spec=DiscoverReferenceDocumentsTaskSpec(root=Path("."), check_urls=True),
    )

    result = DiscoverReferenceDocumentsTaskHandler().handle(record, config, task_repository)

    checked_urls = sorted(
        task.spec.url
        for task in result.new_records
        if isinstance(task.spec, CheckReferenceUrlTaskSpec)
    )
    assert checked_urls == ["https://example.org/bob"]


def test_discover_reference_documents_skips_recheck_for_marked_urls(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    config.output_dir.mkdir(parents=True)
    (config.input_dir / "note.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    (config.output_dir / "references.index.yaml").write_text(
        "version: 1\n"
        "urls:\n"
        "  - url: https://example.org/bob\n"
        "    skip_recheck: true\n"
        "    unused: false\n"
        "    doi: 10.1000/bob\n"
        "    last_checked_at: 2026-05-31T10:00:00Z\n",
        encoding="utf-8",
    )
    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    record = TaskRecord(
        task_key=make_discover_reference_documents_task_key(Path("."), check_urls=True),
        spec=DiscoverReferenceDocumentsTaskSpec(root=Path("."), check_urls=True),
    )

    result = DiscoverReferenceDocumentsTaskHandler().handle(record, config, task_repository)

    checked_urls = [
        task.spec.url
        for task in result.new_records
        if isinstance(task.spec, CheckReferenceUrlTaskSpec)
    ]
    assert checked_urls == []


def test_merge_reference_indexes_handler_reuses_yaml_metadata_for_skipped_urls(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    config.output_dir.mkdir(parents=True)
    (config.input_dir / "alpha.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    (config.output_dir / "references.index.yaml").write_text(
        "version: 1\n"
        "urls:\n"
        "  - url: https://example.org/bob\n"
        "    skip_recheck: true\n"
        "    unused: false\n"
        "    doi: 10.1000/bob\n"
        "    last_checked_at: 2026-05-31T10:00:00Z\n"
        "    http_status_code: 200\n"
        "    reason_phrase: OK\n"
        "    content_type: text/html\n"
        "    filename: bob\n",
        encoding="utf-8",
    )

    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    alpha_task_key = make_index_markdown_references_task_key(Path("alpha.md"), "sha256:alpha")
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

    record = TaskRecord(
        task_key=make_merge_reference_indexes_task_key(
            Path("."),
            [Path("alpha.md")],
            checked_urls=["https://example.org/bob"],
        ),
        spec=MergeReferenceIndexesTaskSpec(
            root=Path("."),
            document_relative_paths=[Path("alpha.md")],
            reference_task_keys=[alpha_task_key],
            url_check_task_keys=[],
        ),
        child_task_keys=[alpha_task_key],
    )

    result = MergeReferenceIndexesTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert (config.output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/bob\n\n"
        "- Status: 200 OK\n"
        "- Last checked: 2026-05-31T10:00:00Z\n"
        "- DOI: [10.1000/bob](https://doi.org/10.1000/bob)\n"
        "- Content-Type: text/html\n"
        "- Filename: bob\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n"
    )


def test_merge_reference_indexes_handler_keeps_unused_url_metadata_in_yaml(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    config.output_dir.mkdir(parents=True)
    (config.output_dir / "references.index.yaml").write_text(
        "version: 1\n"
        "urls:\n"
        "  - url: https://example.org/old\n"
        "    skip_recheck: true\n"
        "    unused: false\n"
        "    doi: 10.1000/old\n"
        "    last_checked_at: 2026-05-31T10:00:00Z\n"
        "    http_status_code: 200\n"
        "    reason_phrase: OK\n"
        "    final_url: https://cdn.example.org/old\n"
        "    content_type: text/html\n"
        "    filename: old\n"
        "    references:\n"
        "      - document_path: old.md\n"
        "        heading_path:\n"
        "          - Sources\n"
        "        label: Old\n",
        encoding="utf-8",
    )

    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    record = TaskRecord(
        task_key=make_merge_reference_indexes_task_key(Path("."), []),
        spec=MergeReferenceIndexesTaskSpec(
            root=Path("."),
            document_relative_paths=[],
            reference_task_keys=[],
            url_check_task_keys=[],
        ),
        child_task_keys=[],
    )

    result = MergeReferenceIndexesTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert yaml.safe_load((config.output_dir / "references.index.yaml").read_text(encoding="utf-8")) == {
        "version": 1,
        "urls": [
            {
                "url": "https://example.org/old",
                "skip_recheck": True,
                "unused": True,
                "doi": "10.1000/old",
                "last_checked_at": "2026-05-31T10:00:00Z",
                "http_status_code": 200,
                "final_url": "https://cdn.example.org/old",
                "content_type": "text/html",
                "filename": "old",
                "reason_phrase": "OK",
                "references": [],
            }
        ],
    }


def test_merge_reference_indexes_handler_keeps_manual_doi_over_auto_detected_doi(
    tmp_path: Path,
) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
    )
    config.input_dir.mkdir(parents=True)
    config.output_dir.mkdir(parents=True)
    (config.input_dir / "alpha.md").write_text(
        "# Sources\n\nSee [Paper](https://doi.org/10.1000/auto).\n",
        encoding="utf-8",
    )
    (config.output_dir / "references.index.yaml").write_text(
        "version: 1\n"
        "urls:\n"
        "  - url: https://doi.org/10.1000/auto\n"
        "    skip_recheck: false\n"
        "    unused: false\n"
        "    doi: 10.1000/manual\n",
        encoding="utf-8",
    )

    task_repository = JsonTaskRepository(config.data_dir / "tasks")
    alpha_task_key = make_index_markdown_references_task_key(Path("alpha.md"), "sha256:alpha")
    url_task_key = make_check_reference_url_task_key("https://doi.org/10.1000/auto")
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
            task_key=url_task_key,
            spec=CheckReferenceUrlTaskSpec(url="https://doi.org/10.1000/auto"),
            status=TaskStatus.SUCCEEDED,
            outcome=TaskOutcome(
                message="URL checked.",
                http_status_code=200,
                result=ReferenceUrlCheckResult(
                    url="https://doi.org/10.1000/auto",
                    checked_at="2026-05-31T10:00:00Z",
                    doi="10.1000/auto",
                    final_url="https://publisher.example/paper",
                    reason_phrase="OK",
                ),
            ),
        )
    )

    record = TaskRecord(
        task_key=make_merge_reference_indexes_task_key(
            Path("."),
            [Path("alpha.md")],
            checked_urls=["https://doi.org/10.1000/auto"],
        ),
        spec=MergeReferenceIndexesTaskSpec(
            root=Path("."),
            document_relative_paths=[Path("alpha.md")],
            reference_task_keys=[alpha_task_key],
            url_check_task_keys=[url_task_key],
        ),
        child_task_keys=[alpha_task_key, url_task_key],
    )

    result = MergeReferenceIndexesTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    rendered = (config.output_dir / "references.index.md").read_text(encoding="utf-8")
    assert "- DOI: [10.1000/manual](https://doi.org/10.1000/manual)" in rendered
    assert yaml.safe_load((config.output_dir / "references.index.yaml").read_text(encoding="utf-8")) == {
        "version": 1,
        "urls": [
            {
                "url": "https://doi.org/10.1000/auto",
                "skip_recheck": False,
                "unused": False,
                "doi": "10.1000/manual",
                "last_checked_at": "2026-05-31T10:00:00Z",
                "http_status_code": 200,
                "final_url": "https://publisher.example/paper",
                "reason_phrase": "OK",
                "references": [
                    {
                        "document_path": "alpha.md",
                        "heading_path": ["Sources"],
                        "label": "Paper",
                    }
                ],
            }
        ],
    }


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
                        "===BEGIN PREVIOUS CONTEXT===\n"
                        "${pre_context}\n"
                        "===END PREVIOUS CONTEXT===\n"
                        "===BEGIN TRANSLATION HINTS===\n"
                        "${translation_hints}\n"
                        "===END TRANSLATION HINTS===\n"
                        "===BEGIN SOURCE TEXT===\n"
                        "${input_fragment}\n"
                        "===END SOURCE TEXT===\n"
                        "===BEGIN FOLLOWING CONTEXT===\n"
                        "${post_context}\n"
                        "===END FOLLOWING CONTEXT===\n"
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
            pre_context="Before context.",
            post_context="After context.",
            fragment_digest="sha256:frag",
            profile_name="technical",
            profile_digest="sha256:profile",
            translation_hints="Prefer maritime vocabulary.",
        ),
    )

    result = TranslateFragmentTaskHandler(llm_client=llm_client).handle(record, config)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert result.updated_record.outcome is not None
    assert result.updated_record.outcome.result == TranslatedFragmentResult(
        translated_text="# INTRO",
        length=7,
    )
    assert '"content":"===BEGIN PREVIOUS CONTEXT===\\nBefore context.\\n===END PREVIOUS CONTEXT===\\n===BEGIN TRANSLATION HINTS===\\nPrefer maritime vocabulary.\\n===END TRANSLATION HINTS===\\n===BEGIN SOURCE TEXT===\\n# Intro\\n===END SOURCE TEXT===\\n===BEGIN FOLLOWING CONTEXT===\\nAfter context.\\n===END FOLLOWING CONTEXT===\\n"' in str(
        captured_payload["payload"]
    )


def test_discover_translate_fragments_builds_bounded_neighbor_context(tmp_path: Path) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    max_pre_context_bytes=len("# Intro\n\nBefore one.".encode("utf-8")),
                    max_post_context_bytes=len("After two.\n\nTail.".encode("utf-8")),
                    temperature=0.0,
                    system_prompt="You are a translator.",
                    user_prompt="${pre_context}\n${input_fragment}\n${post_context}",
                )
            }
        ),
    )
    config.input_dir.mkdir(parents=True)
    (config.input_dir / "note.md").write_text(
        "# Intro\n\nBefore one.\n\nTarget frag.\n\nAfter two.\n\nTail.\n",
        encoding="utf-8",
    )

    record = TaskRecord(
        task_key="task:discover_translate_document_fragments:abc",
        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
            relative_path=Path("note.md"),
            source_digest="sha256:doc",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = DiscoverTranslateDocumentFragmentsTaskHandler().handle(
        record,
        config,
        JsonTaskRepository(config.data_dir / "tasks"),
    )

    target_record = next(
        created_record
        for created_record in result.new_records
        if created_record.spec.kind == "translate_fragment"
        and created_record.spec.text == "Target frag."
    )

    assert target_record.spec.pre_context == "# Intro\n\nBefore one."
    assert target_record.spec.post_context == "After two.\n\nTail."


def test_discover_translate_fragments_excludes_fenced_blocks_from_neighbor_context(
    tmp_path: Path,
) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    max_pre_context_bytes=4096,
                    max_post_context_bytes=4096,
                    temperature=0.0,
                    system_prompt="You are a translator.",
                    user_prompt="${pre_context}\n${input_fragment}\n${post_context}",
                )
            }
        ),
    )
    config.input_dir.mkdir(parents=True)
    (config.input_dir / "note.md").write_text(
        "# Intro\n\n"
        "Useful before.\n\n"
        "```yaml\n"
        "schema: value\n"
        "```\n\n"
        "Target frag.\n\n"
        "```mermaid\n"
        "graph TD\n"
        "```\n\n"
        "Useful after.\n",
        encoding="utf-8",
    )

    record = TaskRecord(
        task_key="task:discover_translate_document_fragments:abc",
        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
            relative_path=Path("note.md"),
            source_digest="sha256:doc",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = DiscoverTranslateDocumentFragmentsTaskHandler().handle(
        record,
        config,
        JsonTaskRepository(config.data_dir / "tasks"),
    )

    target_record = next(
        created_record
        for created_record in result.new_records
        if created_record.spec.kind == "translate_fragment"
        and created_record.spec.text == "Target frag."
    )

    assert target_record.spec.pre_context == "# Intro\n\nUseful before."
    assert target_record.spec.post_context == "Useful after."


def test_discover_translate_fragments_can_group_multiple_fragments_into_one_task(
    tmp_path: Path,
) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    max_pre_context_bytes=10,
                    max_post_context_bytes=0,
                    max_total_text_bytes=18,
                    max_input_fragment_bytes=10,
                    temperature=0.0,
                    system_prompt="You are a translator.",
                    user_prompt="${pre_context}\n${input_fragment}\n${post_context}",
                )
            }
        ),
    )
    config.input_dir.mkdir(parents=True)
    (config.input_dir / "note.md").write_text(
        "One.\n\nTwo.\n\nThree.\n",
        encoding="utf-8",
    )

    record = TaskRecord(
        task_key="task:discover_translate_document_fragments:abc",
        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
            relative_path=Path("note.md"),
            source_digest="sha256:doc",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = DiscoverTranslateDocumentFragmentsTaskHandler().handle(
        record,
        config,
        JsonTaskRepository(config.data_dir / "tasks"),
    )

    fragment_records = [
        created_record
        for created_record in result.new_records
        if created_record.spec.kind == "translate_fragment"
    ]

    assert len(fragment_records) == 2
    assert fragment_records[0].spec.input_markdown == "One.\n\nTwo."
    assert fragment_records[1].spec.input_markdown == "Three."


def test_discover_translate_fragments_can_absorb_trailing_post_context_at_document_end(
    tmp_path: Path,
) -> None:
    config = WorkspaceConfig(
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        data_dir=tmp_path / "data",
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    max_pre_context_bytes=0,
                    max_post_context_bytes=5,
                    max_total_text_bytes=14,
                    max_input_fragment_bytes=30,
                    temperature=0.0,
                    system_prompt="You are a translator.",
                    user_prompt="${pre_context}\n${input_fragment}\n${post_context}",
                )
            }
        ),
    )
    config.input_dir.mkdir(parents=True)
    (config.input_dir / "note.md").write_text(
        "Target.\n\nTail.\n",
        encoding="utf-8",
    )

    record = TaskRecord(
        task_key="task:discover_translate_document_fragments:abc",
        spec=DiscoverTranslateDocumentFragmentsTaskSpec(
            relative_path=Path("note.md"),
            source_digest="sha256:doc",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
    )

    result = DiscoverTranslateDocumentFragmentsTaskHandler().handle(
        record,
        config,
        JsonTaskRepository(config.data_dir / "tasks"),
    )

    fragment_records = [
        created_record
        for created_record in result.new_records
        if created_record.spec.kind == "translate_fragment"
    ]

    assert len(fragment_records) == 1
    assert fragment_records[0].spec.input_markdown == "Target.\n\nTail."
    assert fragment_records[0].spec.post_context == ""


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
                    user_prompt="${input_fragment}",
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
                    user_prompt="${input_fragment}",
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
    assert result.updated_record.outcome.http_status_code == 503


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
                    user_prompt="${input_fragment}",
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


def test_merge_translated_fragments_writes_optional_header_and_footer(tmp_path: Path) -> None:
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
            "sha256:render",
        ),
        spec=MergeTranslatedFragmentsTaskSpec(
            document_relative_path=Path("note.md"),
            source_digest="sha256:doc",
            fragment_task_keys=fragment_task_keys,
            profile_name="technical",
            profile_digest="sha256:profile",
            render_digest="sha256:render",
            translated_document_header="<!-- Translated automatically -->",
            translated_document_footer="<!-- End automatic translation -->",
        ),
    )

    result = MergeTranslatedFragmentsTaskHandler().handle(record, config, task_repository)

    assert result.updated_record.status == TaskStatus.SUCCEEDED
    assert (config.output_dir / "note.md").read_text(encoding="utf-8") == (
        "<!-- Translated automatically -->\n\n"
        "# INTRO\n\n"
        "ALPHA BETA.\n\n"
        "<!-- End automatic translation -->\n"
    )