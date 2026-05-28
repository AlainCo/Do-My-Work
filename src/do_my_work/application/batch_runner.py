import logging
from pathlib import Path

from do_my_work.application.workflow_engine import WorkflowEngine
from do_my_work.domain.models import BatchRunResult, WorkflowRunResult, WorkspaceConfig


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

    def run_copy_tree(self, config: WorkspaceConfig, root: Path = Path(".")) -> WorkflowRunResult:
        self._logger.info(
            "Running Markdown document copy workflow with root=%s input=%s output=%s data=%s",
            root,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return WorkflowEngine().run(config, root=root, request_kind="copy_tree")

    def run_summary_document_tree(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
    ) -> WorkflowRunResult:
        self._logger.info(
            "Running Markdown fragment summary workflow with root=%s input=%s output=%s data=%s",
            root,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return WorkflowEngine().run(config, root=root, request_kind="summary_document_tree")