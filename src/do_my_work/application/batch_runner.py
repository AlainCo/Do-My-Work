import logging

from do_my_work.domain.models import BatchRunResult, WorkspaceConfig


class BatchRunner:
    """Minimal batch orchestrator.

    This is the future home for the workflow coordination logic.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def run(self, config: WorkspaceConfig) -> BatchRunResult:
        self._logger.info(
            "Running batch with input=%s output=%s data=%s",
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        message = "Workspace configuration loaded."
        return BatchRunResult(message=message, workspace=config)