from pathlib import Path

from do_my_work.application.spurious_file_report import SpuriousFileReporter
from do_my_work.domain.models import FileSelectionConfig, FileSelectionRule, WorkspaceConfig


def test_spurious_file_report_respects_workspace_and_local_ignores(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = output_dir / "work" / "data"

    (input_dir / "docs").mkdir(parents=True)
    (input_dir / "docs" / "note.md").write_text("# Intro\n", encoding="utf-8")
    (input_dir / "docs" / "do-my-work.yaml").write_text(
        "version: 1\n"
        "spurious:\n"
        "  rules:\n"
        "    - match: \"manual/**/*\"\n"
        "      exclude: true\n",
        encoding="utf-8",
    )
    (input_dir / "assets").mkdir(parents=True)
    (input_dir / "assets" / "logo.jpeg").write_bytes(b"jpeg-bytes")

    (output_dir / "docs").mkdir(parents=True)
    (output_dir / "docs" / "note.md").write_text("translated", encoding="utf-8")
    (output_dir / "docs" / "old.md").write_text("stale", encoding="utf-8")
    (output_dir / "docs" / "manual").mkdir(parents=True)
    (output_dir / "docs" / "manual" / "keep.md").write_text("manual", encoding="utf-8")
    (output_dir / "assets").mkdir(parents=True)
    (output_dir / "assets" / "logo.jpeg").write_bytes(b"jpeg-bytes")
    (output_dir / "note.references.md").write_text("ignore", encoding="utf-8")
    data_dir.mkdir(parents=True)
    (data_dir / "task.json").write_text("{}", encoding="utf-8")

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
        resource_selection=FileSelectionConfig(
            default_action="exclude",
            rules=[FileSelectionRule(match="assets/**/*.jpeg", action="include")],
        ),
        spurious_detection=FileSelectionConfig(
            default_action="include",
            rules=[FileSelectionRule(match="manual/**/*", action="exclude")],
        ),
    )

    result = SpuriousFileReporter().build_report(config)

    assert result.checked_file_count == 3
    assert result.ignored_file_count == 3
    assert result.spurious_files == [Path("docs/old.md")]
    assert result.spurious_translated_files == [Path("docs/old.md")]
    assert result.spurious_resource_files == []
    assert result.spurious_other_files == []
    assert result.expected_translated_file_count == 1
    assert result.expected_resource_file_count == 1


def test_spurious_file_report_classifies_spurious_resource_outputs(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    data_dir = output_dir / "work" / "data"

    (input_dir / "assets").mkdir(parents=True)
    (input_dir / "assets" / "logo.jpeg").write_bytes(b"jpeg-bytes")

    (output_dir / "assets").mkdir(parents=True)
    (output_dir / "assets" / "logo.jpeg").write_bytes(b"jpeg-bytes")
    (output_dir / "assets" / "old.jpeg").write_bytes(b"stale-jpeg-bytes")
    data_dir.mkdir(parents=True)

    config = WorkspaceConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        data_dir=data_dir,
        resource_selection=FileSelectionConfig(
            default_action="exclude",
            rules=[FileSelectionRule(match="assets/**/*.jpeg", action="include")],
        ),
        spurious_detection=FileSelectionConfig(default_action="include"),
    )

    result = SpuriousFileReporter().build_report(config)

    assert result.checked_file_count == 2
    assert result.ignored_file_count == 0
    assert result.spurious_files == [Path("assets/old.jpeg")]
    assert result.spurious_translated_files == []
    assert result.spurious_resource_files == [Path("assets/old.jpeg")]
    assert result.spurious_other_files == []
    assert result.expected_translated_file_count == 0
    assert result.expected_resource_file_count == 1