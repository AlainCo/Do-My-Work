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
        check_urls: bool = False,
    ) -> WorkflowRunResult:
        self._logger.info(
            "Running Markdown reference index workflow with root=%s check_urls=%s input=%s output=%s data=%s",
            root,
            check_urls,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return WorkflowEngine().run(
            config,
            root=root,
            request_kind="reference_index_tree",
            check_urls=check_urls,
        )

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
        with_review: bool = False,
    ) -> WorkflowRunResult:
        self._logger.info(
            "Running Markdown fragment translation workflow with root=%s "
            "profile=%s with_review=%s input=%s output=%s data=%s",
            root,
            translator_profile,
            with_review,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return WorkflowEngine().run(
            config,
            root=root,
            request_kind="translate_document_tree",
            translator_profile=translator_profile,
            with_review=with_review,
        )

    def run_spurious_file_report(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
        report_dir: Path | None = None,
    ) -> SpuriousFileReportResult:
        self._logger.info(
            "Running spurious output file report with root=%s input=%s output=%s data=%s",
            root,
            config.input_dir,
            config.output_dir,
            config.data_dir,
        )
        return SpuriousFileReporter().build_report(config, root=root, report_dir=report_dir)

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