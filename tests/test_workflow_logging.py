from pathlib import Path

from do_my_work.application.workflow_engine import WorkflowEngine
from do_my_work.domain.models import WorkspaceConfig


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
    (output_dir / "alpha.md").unlink()

    with caplog.at_level("INFO"):
        WorkflowEngine().run(config, root=Path("."))

    assert "Task revalidated:" in caplog.text
    assert "old_status=succeeded new_status=pending" in caplog.text
    assert "Executing task:" in caplog.text
    assert "Task completed:" in caplog.text
    assert "Workflow run summary:" in caplog.text
    assert "executed=2" in caplog.text
    assert "replayed=1" in caplog.text


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
    assert "unchanged=2" in caplog.text