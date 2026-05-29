from pathlib import Path

import httpx

from do_my_work.application.workflow_engine import WorkflowEngine
from do_my_work.domain.models import LlmConfig, TranslatorProfileConfig, WorkspaceConfig


def test_workflow_engine_logs_revalidation_and_execution(
    tmp_path: Path,
    caplog,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "alpha.md").write_text("alpha\n", encoding="utf-8")

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    WorkflowEngine().run(config, root=Path("."))
    (output_dir / "alpha.references.md").unlink()

    with caplog.at_level("INFO"):
        WorkflowEngine().run(config, root=Path("."))

    assert "Task revalidated:" in caplog.text
    assert "old_status=succeeded new_status=pending" in caplog.text
    assert "Executing task:" in caplog.text
    assert "Task completed:" in caplog.text
    assert "Workflow run summary:" in caplog.text
    assert "executed=3" in caplog.text
    assert "replayed=1" in caplog.text
    assert "retried_failed=0" in caplog.text


def test_workflow_engine_logs_summary_for_unchanged_run(tmp_path: Path, caplog) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "alpha.md").write_text("alpha\n", encoding="utf-8")

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    WorkflowEngine().run(config, root=Path("."))

    with caplog.at_level("INFO"):
        WorkflowEngine().run(config, root=Path("."))

    assert "Workflow run summary:" in caplog.text
    assert "executed=0" in caplog.text
    assert "replayed=0" in caplog.text
    assert "retried_failed=0" in caplog.text
    assert "unchanged=3" in caplog.text


def test_workflow_engine_logs_when_failed_translation_is_retried(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text("# Intro\n\nAlpha beta.\n", encoding="utf-8")

    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    call_count = {"value": 0}

    def flaky_translate_fragment(self, config, profile_name, parameters):
        del self, config, profile_name
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise httpx.ReadTimeout("temporary timeout")
        return str(parameters["inputfragment"]).upper()

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        flaky_translate_fragment,
    )

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
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

    WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    with caplog.at_level("INFO"):
        WorkflowEngine().run(
            config,
            root=Path("."),
            request_kind="translate_document_tree",
            translator_profile="technical",
        )

    assert "Task retry scheduled:" in caplog.text
    assert "kind=translate_fragment" in caplog.text
    assert "reason=previous_run_failed" in caplog.text
    assert "error_category=timeout" in caplog.text
    assert "http_status_code=None" in caplog.text
    assert "retried_failed=1" in caplog.text


def test_workflow_engine_logs_http_status_code_when_failed_translation_is_retried(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text("# Intro\n\nAlpha beta.\n", encoding="utf-8")

    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    call_count = {"value": 0}

    def flaky_translate_fragment(self, config, profile_name, parameters):
        del self, config, profile_name
        call_count["value"] += 1
        if call_count["value"] == 1:
            request = httpx.Request("POST", "http://mock.example:11434/api/chat")
            response = httpx.Response(
                503,
                request=request,
                json={"error": "temporary outage"},
            )
            raise httpx.HTTPStatusError(
                "Server error '503 Service Unavailable' for url 'http://mock.example:11434/api/chat'",
                request=request,
                response=response,
            )
        return str(parameters["inputfragment"]).upper()

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        flaky_translate_fragment,
    )

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
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

    WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    with caplog.at_level("INFO"):
        WorkflowEngine().run(
            config,
            root=Path("."),
            request_kind="translate_document_tree",
            translator_profile="technical",
        )

    assert "Task retry scheduled:" in caplog.text
    assert "error_category=http_status" in caplog.text
    assert "http_status_code=503" in caplog.text