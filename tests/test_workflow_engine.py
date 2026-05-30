import json
from pathlib import Path

import httpx
import pytest

from do_my_work.application.task_keys import make_translate_fragment_task_key
from do_my_work.application.workflow_engine import WorkflowEngine
from do_my_work.domain.models import TaskRecord, TaskStatus, TranslateFragmentTaskSpec, WorkspaceConfig


def test_workflow_engine_selects_translate_fragment_tasks_grouped_by_document() -> None:
    engine = WorkflowEngine()
    task_records = [
        TaskRecord(
            task_key=make_translate_fragment_task_key(
                Path("zeta.md"),
                "sha256:frag-1",
                "technical",
                "sha256:profile",
            ),
            spec=TranslateFragmentTaskSpec(
                document_relative_path=Path("zeta.md"),
                fragment_kind="paragraph",
                heading_path=[],
                text="Zeta first.",
                pre_context="",
                post_context="",
                fragment_digest="sha256:frag-1",
                profile_name="technical",
                profile_digest="sha256:profile",
            ),
            status=TaskStatus.PENDING,
        ),
        TaskRecord(
            task_key=make_translate_fragment_task_key(
                Path("alpha.md"),
                "sha256:frag-1",
                "technical",
                "sha256:profile",
            ),
            spec=TranslateFragmentTaskSpec(
                document_relative_path=Path("alpha.md"),
                fragment_kind="paragraph",
                heading_path=[],
                text="Alpha first.",
                pre_context="",
                post_context="",
                fragment_digest="sha256:frag-1",
                profile_name="technical",
                profile_digest="sha256:profile",
            ),
            status=TaskStatus.PENDING,
        ),
        TaskRecord(
            task_key=make_translate_fragment_task_key(
                Path("alpha.md"),
                "sha256:frag-2",
                "technical",
                "sha256:profile",
            ),
            spec=TranslateFragmentTaskSpec(
                document_relative_path=Path("alpha.md"),
                fragment_kind="paragraph",
                heading_path=[],
                text="Alpha second.",
                pre_context="",
                post_context="",
                fragment_digest="sha256:frag-2",
                profile_name="technical",
                profile_digest="sha256:profile",
            ),
            status=TaskStatus.PENDING,
        ),
    ]

    ordered_paths: list[Path] = []
    remaining_records = task_records.copy()
    while remaining_records:
        next_task = engine._select_next_task(remaining_records)
        assert next_task is not None
        ordered_paths.append(next_task.spec.document_relative_path)
        remaining_records = [
            record for record in remaining_records if record.task_key != next_task.task_key
        ]

    assert ordered_paths[:2] == [Path("alpha.md"), Path("alpha.md")]
    assert ordered_paths[2] == Path("zeta.md")


def test_workflow_engine_counts_only_active_task_statuses() -> None:
    engine = WorkflowEngine()
    active_task = TaskRecord(
        task_key="task:index_markdown_references:active",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("alpha.md"),
            fragment_kind="paragraph",
            heading_path=[],
            text="Alpha.",
            pre_context="",
            post_context="",
            fragment_digest="sha256:frag-active",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.PENDING,
    )
    unchanged_task = TaskRecord(
        task_key="task:index_markdown_references:unchanged",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("beta.md"),
            fragment_kind="paragraph",
            heading_path=[],
            text="Beta.",
            pre_context="",
            post_context="",
            fragment_digest="sha256:frag-unchanged",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.SUCCEEDED,
    )
    waiting_task = TaskRecord(
        task_key="task:merge_translated_fragments:waiting",
        spec=TranslateFragmentTaskSpec(
            document_relative_path=Path("gamma.md"),
            fragment_kind="paragraph",
            heading_path=[],
            text="Gamma.",
            pre_context="",
            post_context="",
            fragment_digest="sha256:frag-waiting",
            profile_name="technical",
            profile_digest="sha256:profile",
        ),
        status=TaskStatus.WAITING,
    )

    counts = engine._build_active_task_status_counts(
        [active_task, unchanged_task, waiting_task],
        {unchanged_task.task_key},
    )

    assert counts[TaskStatus.PENDING] == 1
    assert counts[TaskStatus.WAITING] == 1
    assert counts[TaskStatus.SUCCEEDED] == 0
    assert counts[TaskStatus.FAILED] == 0


def test_workflow_engine_runs_reference_index_flow(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    (input_dir / "nested").mkdir(parents=True)
    (input_dir / "nested" / "other.md").write_text(
        "# Further Reading\n\nSee [Alice](https://example.org/alice).\n",
        encoding="utf-8",
    )

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    run_request = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="reference_index_tree",
    )

    assert run_request.status == "succeeded"
    assert run_request.summary.executed_task_count == 4
    assert run_request.summary.retried_failed_task_count == 0
    assert run_request.summary.created_task_count == 3
    assert run_request.summary.pending_task_count == 0
    assert run_request.summary.waiting_task_count == 0
    assert run_request.summary.succeeded_task_count == 4
    assert run_request.summary.failed_task_count == 0
    assert (output_dir / "note.references.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Index\n\n"
        "Source: note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )
    assert (output_dir / "nested" / "other.references.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Index\n\n"
        "Source: nested/other.md\n\n"
        "- [Alice](https://example.org/alice) [Further Reading]\n"
    )
    assert (output_dir / "references.index.md").read_text(encoding="utf-8") == (
        "# Markdown Reference Tree Index\n\n"
        "## nested/other.md\n\n"
        "- [Alice](https://example.org/alice) [Further Reading]\n\n"
        "## note.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").rglob("*.json"))
    ]
    assert len(persisted_tasks) == 4
    assert sorted(task.spec.kind for task in persisted_tasks) == [
        "discover_reference_documents",
        "index_markdown_references",
        "index_markdown_references",
        "merge_reference_indexes",
    ]


def test_workflow_engine_applies_workspace_file_selection_to_reference_index(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    (input_dir / "docs").mkdir(parents=True)
    (input_dir / "docs" / "keep.md").write_text(
        "# Kept\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    (input_dir / "docs" / "drafts").mkdir(parents=True)
    (input_dir / "docs" / "drafts" / "skip.md").write_text(
        "# Skip\n\nSee [Skip](https://example.org/skip).\n",
        encoding="utf-8",
    )
    (input_dir / "docs" / "drafts" / "reviewed").mkdir(parents=True)
    (input_dir / "docs" / "drafts" / "reviewed" / "back.md").write_text(
        "# Back\n\nSee [Alice](https://example.org/alice).\n",
        encoding="utf-8",
    )
    (input_dir / "outside.md").write_text(
        "# Outside\n\nSee [Out](https://example.org/out).\n",
        encoding="utf-8",
    )

    from do_my_work.domain.models import FileSelectionConfig, FileSelectionRule

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
        file_selection=FileSelectionConfig(
            default_action="exclude",
            rules=[
                FileSelectionRule(match="docs/**/*.md", action="include"),
                FileSelectionRule(match="docs/drafts/**/*.md", action="exclude"),
                FileSelectionRule(match="docs/drafts/reviewed/**/*.md", action="include"),
            ],
        ),
    )

    run_request = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="reference_index_tree",
    )

    assert run_request.status == "succeeded"
    assert (output_dir / "docs" / "keep.references.md").exists()
    assert not (output_dir / "docs" / "drafts" / "skip.references.md").exists()
    assert (output_dir / "docs" / "drafts" / "reviewed" / "back.references.md").exists()
    assert not (output_dir / "outside.references.md").exists()


def test_workflow_engine_runs_translation_flow_via_fragment_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n\n- Item one\n",
        encoding="utf-8",
    )

    from do_my_work.domain.models import LlmConfig, TranslatorProfileConfig
    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        lambda self, config, profile_name, parameters: (
            self._record_attempt_duration(1.0),
            str(parameters["input_fragment"]).upper(),
        )[1],
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
                        "${input_fragment}\n"
                        "===END SOURCE TEXT===\n"
                    ),
                )
            }
        ),
    )

    run_request = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert run_request.status == "succeeded"
    assert run_request.summary.executed_task_count == 6
    assert run_request.summary.retried_failed_task_count == 0
    assert run_request.summary.created_task_count == 5
    assert run_request.summary.pending_task_count == 0
    assert run_request.summary.waiting_task_count == 0
    assert run_request.summary.succeeded_task_count == 6
    assert run_request.summary.failed_task_count == 0
    assert run_request.summary.llm_call_attempt_count == 3
    assert run_request.summary.llm_call_average_seconds == 1.0
    assert run_request.summary.llm_call_variance_seconds == 0.0
    assert (output_dir / "note.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n\n- ITEM ONE\n"
    )

    persisted_tasks = [
        TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted((data_dir / "tasks").rglob("*.json"))
    ]
    assert len(persisted_tasks) == 6
    assert sorted(task.spec.kind for task in persisted_tasks) == [
        "discover_translate_document_fragments",
        "discover_translate_documents",
        "merge_translated_fragments",
        "translate_fragment",
        "translate_fragment",
        "translate_fragment",
    ]


def test_workflow_engine_applies_workspace_file_selection_to_translation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    (input_dir / "docs").mkdir(parents=True)
    (input_dir / "docs" / "keep.md").write_text(
        "# Intro\n\nAlpha beta.\n",
        encoding="utf-8",
    )
    (input_dir / "docs" / "skip.tmp.md").write_text(
        "# Skip\n\nShould not translate.\n",
        encoding="utf-8",
    )

    from do_my_work.domain.models import (
        FileSelectionConfig,
        FileSelectionRule,
        LlmConfig,
        TranslatorProfileConfig,
    )
    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        lambda self, config, profile_name, parameters: str(parameters["input_fragment"]).upper(),
    )

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
        file_selection=FileSelectionConfig(
            default_action="exclude",
            rules=[
                FileSelectionRule(match="docs/**/*.md", action="include"),
                FileSelectionRule(match="**/*.tmp.md", action="exclude"),
            ],
        ),
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="ollama-mock",
                    temperature=0.0,
                    system_prompt="You are a professional translatoir from french to english.",
                    user_prompt=(
                        "===BEGIN SOURCE TEXT===\n"
                        "${input_fragment}\n"
                        "===END SOURCE TEXT===\n"
                    ),
                )
            }
        ),
    )

    run_request = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert run_request.status == "succeeded"
    assert (output_dir / "docs" / "keep.md").read_text(encoding="utf-8") == (
        "# INTRO\n\nALPHA BETA.\n"
    )
    assert not (output_dir / "docs" / "skip.tmp.md").exists()


def test_workflow_engine_retries_failed_translation_tasks_on_next_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n",
        encoding="utf-8",
    )

    from do_my_work.domain.models import LlmConfig, TranslatorProfileConfig
    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    call_count = {"value": 0}

    def flaky_translate_fragment(self, config, profile_name, parameters):
        del self, config, profile_name
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise httpx.ReadTimeout("temporary timeout")
        return str(parameters["input_fragment"]).upper()

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
                        "${input_fragment}\n"
                        "===END SOURCE TEXT===\n"
                    ),
                )
            }
        ),
    )

    first_run = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert first_run.status == "failed"
    assert first_run.summary.retried_failed_task_count == 0

    second_run = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert second_run.status == "succeeded"
    assert second_run.summary.retried_failed_task_count == 1
    assert (output_dir / "note.md").read_text(encoding="utf-8") == "# INTRO\n\nALPHA BETA.\n"


def test_workflow_engine_rerenders_translated_document_when_header_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"

    input_dir.mkdir(parents=True)
    (input_dir / "note.md").write_text(
        "# Intro\n\nAlpha beta.\n",
        encoding="utf-8",
    )

    from do_my_work.domain.models import LlmConfig, TranslatorProfileConfig
    from do_my_work.infrastructure.ollama_client import OllamaChatClient

    monkeypatch.setattr(
        OllamaChatClient,
        "translate_fragment",
        lambda self, config, profile_name, parameters: str(parameters["input_fragment"]).upper(),
    )

    base_profile = TranslatorProfileConfig(
        url="http://mock.example:11434",
        model="ollama-mock",
        temperature=0.0,
        system_prompt="You are a professional translatoir from french to english.",
        user_prompt=(
            "===BEGIN SOURCE TEXT===\n"
            "${input_fragment}\n"
            "===END SOURCE TEXT===\n"
        ),
    )
    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
        llm=LlmConfig(translator={"technical": base_profile}),
    )

    first_run = WorkflowEngine().run(
        config,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    config_with_header = config.model_copy(
        update={
            "llm": LlmConfig(
                translator={
                    "technical": base_profile.model_copy(
                        update={
                            "translated_document_header": "<!-- Translated automatically -->",
                            "translated_document_footer": "<!-- End automatic translation -->",
                        }
                    )
                }
            )
        }
    )

    second_run = WorkflowEngine().run(
        config_with_header,
        root=Path("."),
        request_kind="translate_document_tree",
        translator_profile="technical",
    )

    assert first_run.status == "succeeded"
    assert second_run.status == "succeeded"
    assert second_run.summary.executed_task_count == 3
    assert second_run.summary.created_task_count == 2
    assert (output_dir / "note.md").read_text(encoding="utf-8") == (
        "<!-- Translated automatically -->\n\n"
        "# INTRO\n\n"
        "ALPHA BETA.\n\n"
        "<!-- End automatic translation -->\n"
    )