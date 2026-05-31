import logging
from dataclasses import dataclass
from pathlib import Path

from do_my_work.application.task_handlers import (
    _is_selected_path,
    _iter_applicable_local_workflow_configs,
    _iter_markdown_documents,
    _iter_resource_files,
    _path_matches_rule,
)
from do_my_work.domain.models import LocalWorkflowConfig, WorkspaceConfig
from do_my_work.infrastructure.markdown_reference_report import build_root_reference_index_path


@dataclass(frozen=True, slots=True)
class SpuriousFileReportResult:
    report_path: Path
    checked_file_count: int
    ignored_file_count: int
    spurious_files: list[Path]
    expected_translated_file_count: int
    expected_resource_file_count: int

    @property
    def spurious_file_count(self) -> int:
        return len(self.spurious_files)


class SpuriousFileReporter:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def build_report(
        self,
        config: WorkspaceConfig,
        root: Path = Path("."),
    ) -> SpuriousFileReportResult:
        input_root = config.input_dir / root
        if not input_root.exists():
            raise FileNotFoundError(input_root)

        expected_translated_outputs = {
            document.relative_path
            for document in _iter_markdown_documents(
                input_root,
                config,
                workflow_kind="translate_document_tree",
            )
        }
        expected_resource_outputs = {
            source_path.relative_to(config.input_dir)
            for source_path in _iter_resource_files(input_root, config)
        }
        expected_outputs = expected_translated_outputs | expected_resource_outputs

        output_root = config.output_dir / root
        checked_files: list[Path] = []
        ignored_file_count = 0
        spurious_files: list[Path] = []

        if output_root.exists():
            for output_path in sorted(output_root.rglob("*")):
                if not output_path.is_file():
                    continue

                relative_output_path = output_path.relative_to(config.output_dir)
                if not _should_check_output_file(relative_output_path, config):
                    ignored_file_count += 1
                    continue

                checked_files.append(relative_output_path)
                if relative_output_path not in expected_outputs:
                    spurious_files.append(relative_output_path)

        report_path = config.output_dir / build_spurious_file_report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            render_spurious_file_report(
                root=root,
                checked_files=checked_files,
                spurious_files=spurious_files,
                expected_translated_file_count=len(expected_translated_outputs),
                expected_resource_file_count=len(expected_resource_outputs),
                ignored_file_count=ignored_file_count,
            ),
            encoding="utf-8",
        )

        self._logger.info(
            "Spurious file report written: path=%s checked=%s ignored=%s spurious=%s expected_translated=%s expected_resources=%s",
            report_path,
            len(checked_files),
            ignored_file_count,
            len(spurious_files),
            len(expected_translated_outputs),
            len(expected_resource_outputs),
        )

        return SpuriousFileReportResult(
            report_path=report_path,
            checked_file_count=len(checked_files),
            ignored_file_count=ignored_file_count,
            spurious_files=spurious_files,
            expected_translated_file_count=len(expected_translated_outputs),
            expected_resource_file_count=len(expected_resource_outputs),
        )


def build_spurious_file_report_path() -> Path:
    return Path("spurious-files.md")


def render_spurious_file_report(
    root: Path,
    checked_files: list[Path],
    spurious_files: list[Path],
    expected_translated_file_count: int,
    expected_resource_file_count: int,
    ignored_file_count: int,
) -> str:
    lines = [
        "# Spurious Output File Report",
        "",
        f"Root: {root.as_posix()}",
        "",
        f"- Expected translated documents: {expected_translated_file_count}",
        f"- Expected copied resources: {expected_resource_file_count}",
        f"- Checked output files: {len(checked_files)}",
        f"- Ignored output files: {ignored_file_count}",
        f"- Spurious output files: {len(spurious_files)}",
        "",
    ]

    if not spurious_files:
        lines.extend([
            "## Spurious Files",
            "",
            "None.",
            "",
        ])
        return "\n".join(lines)

    lines.extend(["## Spurious Files", ""])
    lines.extend(f"- {path.as_posix()}" for path in spurious_files)
    lines.append("")
    return "\n".join(lines)


def _should_check_output_file(relative_output_path: Path, config: WorkspaceConfig) -> bool:
    if relative_output_path == build_spurious_file_report_path():
        return False
    if relative_output_path == build_root_reference_index_path():
        return False
    if relative_output_path.name.endswith(".references.md"):
        return False
    if _is_under_data_dir(relative_output_path, config):
        return False
    if not _is_selected_path(relative_output_path, config.spurious_detection):
        return False
    if not _is_allowed_by_local_spurious_rules(relative_output_path, config):
        return False
    return True


def _is_under_data_dir(relative_output_path: Path, config: WorkspaceConfig) -> bool:
    try:
        data_relative_path = config.data_dir.relative_to(config.output_dir)
    except ValueError:
        return False

    if data_relative_path == Path("."):
        return True
    return relative_output_path == data_relative_path or data_relative_path in relative_output_path.parents


def _is_allowed_by_local_spurious_rules(relative_output_path: Path, config: WorkspaceConfig) -> bool:
    local_config_cache: dict[Path, LocalWorkflowConfig | None] = {}
    input_shadow_path = config.input_dir / relative_output_path

    for directory, local_config in _iter_applicable_local_workflow_configs(
        input_shadow_path,
        config.input_dir,
        local_config_cache,
    ):
        relative_to_directory = input_shadow_path.relative_to(directory)
        for rule in local_config.spurious.rules:
            if _path_matches_rule(relative_to_directory, rule.match) and rule.exclude:
                return False

    return True