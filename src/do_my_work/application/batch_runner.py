import logging
from pathlib import Path
import shutil

from do_my_work.application.spurious_file_report import SpuriousFileReportResult, SpuriousFileReporter
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

    def run_copy_resource_tree(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
    ) -> WorkflowRunResult:
        self._logger.info(
            "Running resource copy workflow with root=%s input=%s output=%s data=%s",
            root,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return WorkflowEngine().run(config, root=root, request_kind="copy_resource_tree")

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

    def run_spurious_file_report(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
    ) -> SpuriousFileReportResult:
        self._logger.info(
            "Running spurious output file report with root=%s input=%s output=%s data=%s",
            root,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return SpuriousFileReporter().build_report(config, root=root)

    def clean_tasks(self, config: WorkspaceConfig) -> int:
        tasks_dir = config.data_dir / "tasks"
        if not tasks_dir.exists():
            self._logger.info("No workflow task directory to clean: %s", tasks_dir)
            return 0

        removed_task_count = sum(1 for _ in tasks_dir.rglob("*.json"))
        shutil.rmtree(tasks_dir)
        self._logger.info(
            "Removed workflow task directory: %s (task_files=%s)",
            tasks_dir,
            removed_task_count,
        )
        return removed_task_count