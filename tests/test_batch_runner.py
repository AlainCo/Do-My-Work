from do_my_work.application.batch_runner import BatchRunner
from do_my_work.domain.models import WorkspaceConfig


def test_batch_runner_exposes_workspace_configuration() -> None:
    config = WorkspaceConfig(input_dir="incoming", output_dir="published", data_dir="state")

    result = BatchRunner().run(config)

    assert result.message == "Workspace configuration loaded."
    assert result.workspace.input_dir == config.input_dir
    assert result.workspace.output_dir == config.output_dir
    assert result.workspace.data_dir == config.data_dir