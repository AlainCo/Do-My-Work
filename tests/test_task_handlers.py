from pathlib import Path

from do_my_work.application.task_handlers import CopyFileTaskHandler, DiscoverDocumentsTaskHandler
from do_my_work.application.task_keys import make_copy_task_key, make_discover_documents_task_key
from do_my_work.domain.models import (
    CopyFileTaskSpec,
    DiscoverDocumentsTaskSpec,
    TaskRecord,
    TaskStatus,
    WorkspaceConfig,
)
from do_my_work.infrastructure.json_workflow_store import JsonTaskRepository


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