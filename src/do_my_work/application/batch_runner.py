import logging
from pathlib import Path

from do_my_work.application.workflow_engine import WorkflowEngine
from do_my_work.domain.models import WorkflowRunResult, WorkspaceConfig


class BatchRunner:
    """Minimal batch orchestrator.

    This is the future home for the workflow coordination logic.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def run_reference_index_tree(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
    ) -> WorkflowRunResult:
        self._logger.info(
            "Running Markdown reference index workflow with root=%s input=%s output=%s data=%s",
            root,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return WorkflowEngine().run(config, root=root, request_kind="reference_index_tree")

    def run_translate_document_tree(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
        translator_profile: str = "technical",
    ) -> WorkflowRunResult:
        self._logger.info(
            "Running Markdown fragment translation workflow with root=%s "
            "profile=%s input=%s output=%s data=%s",
            root,
            translator_profile,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return WorkflowEngine().run(
            config,
            root=root,
            request_kind="translate_document_tree",
            translator_profile=translator_profile,
        )