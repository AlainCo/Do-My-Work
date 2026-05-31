from pathlib import Path

from do_my_work.domain.models import ReferenceUrlIndexEntry
from do_my_work.infrastructure.markdown_reference_report import (
    build_root_reference_index_path,
    build_root_reference_index_yaml_path,
    extract_markdown_references,
    render_markdown_reference_report,
    render_tree_markdown_reference_report,
)


def test_extract_markdown_references_keeps_heading_context(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text(
        """# Sources

See [Bob& al, cuisine appliquee, 1984](https://www.cooking.org/bob1984.html).

## More

- [Alice, sauce reduction](https://example.org/alice)
""",
        encoding="utf-8",
    )

    references = extract_markdown_references(source_file)

    assert [
        (reference.heading_path, reference.label, reference.url)
        for reference in references
    ] == [
        (
            ["Sources"],
            "Bob& al, cuisine appliquee, 1984",
            "https://www.cooking.org/bob1984.html",
        ),
        (
            ["Sources", "More"],
            "Alice, sauce reduction",
            "https://example.org/alice",
        ),
    ]


def test_render_markdown_reference_report_outputs_markdown_index(tmp_path: Path) -> None:
    source_file = tmp_path / "nested" / "sample.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )

    report = render_markdown_reference_report(source_file=source_file, source_root=tmp_path)

    assert report == (
        "# Markdown Reference Index\n\n"
        "Source: nested/sample.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
    )


def test_render_tree_markdown_reference_report_outputs_root_index(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir(parents=True)
    (tmp_path / "alpha.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n\n## More\n\nSee [Shared](https://example.org/shared).\n",
        encoding="utf-8",
    )
    (tmp_path / "nested" / "beta.md").write_text(
        "# Further Reading\n\nSee [Alice](https://example.org/alice).\n\nSee [Shared reference](https://example.org/shared).\n",
        encoding="utf-8",
    )

    report = render_tree_markdown_reference_report(
        source_root=tmp_path,
        relative_paths=[Path("alpha.md"), Path("nested/beta.md")],
    )

    assert report == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n"
        "- [Shared](https://example.org/shared) [Sources / More]\n\n"
        "## nested/beta.md\n\n"
        "- [Alice](https://example.org/alice) [Further Reading]\n"
        "- [Shared reference](https://example.org/shared) [Further Reading]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/alice\n\n"
        "References:\n"
        "- nested/beta.md [Further Reading] Alice\n\n"
        "### https://example.org/bob\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n\n"
        "### https://example.org/shared\n\n"
        "References:\n"
        "- alpha.md [Sources / More] Shared\n"
        "- nested/beta.md [Further Reading] Shared reference\n"
    )
    assert build_root_reference_index_path() == Path("references.index.md")
    assert build_root_reference_index_yaml_path() == Path("references.index.yaml")


def test_render_tree_markdown_reference_report_skips_documents_without_references(
    tmp_path: Path,
) -> None:
    (tmp_path / "nested").mkdir(parents=True)
    (tmp_path / "alpha.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )
    (tmp_path / "nested" / "empty.md").write_text(
        "# Empty\n\nNo link here.\n",
        encoding="utf-8",
    )

    report = render_tree_markdown_reference_report(
        source_root=tmp_path,
        relative_paths=[Path("alpha.md"), Path("nested/empty.md")],
    )

    assert report == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/bob\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n"
    )


def test_render_tree_markdown_reference_report_includes_url_check_metadata(
    tmp_path: Path,
) -> None:
    (tmp_path / "alpha.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/files/report.pdf).\n",
        encoding="utf-8",
    )

    report = render_tree_markdown_reference_report(
        source_root=tmp_path,
        relative_paths=[Path("alpha.md")],
        url_index_entries={
            "https://example.org/files/report.pdf": ReferenceUrlIndexEntry(
                url="https://example.org/files/report.pdf",
                last_checked_at="2026-05-31T10:00:00Z",
                doi="10.1000/report",
                http_status_code=200,
                reason_phrase="OK",
                final_url="https://cdn.example.org/report.pdf",
                content_type="application/pdf",
                filename="report.pdf",
            )
        },
    )

    assert report == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Bob](https://example.org/files/report.pdf) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/files/report.pdf\n\n"
        "- Status: 200 OK\n"
        "- Last checked: 2026-05-31T10:00:00Z\n"
        "- DOI: [10.1000/report](https://doi.org/10.1000/report)\n"
        "- Content-Type: application/pdf\n"
        "- Filename: report.pdf\n"
        "- Final URL: https://cdn.example.org/report.pdf\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n"
    )


def test_render_tree_markdown_reference_report_includes_html_preview_metadata(
    tmp_path: Path,
) -> None:
    (tmp_path / "alpha.md").write_text(
        "# Sources\n\nSee [Bob](https://example.org/article).\n",
        encoding="utf-8",
    )

    report = render_tree_markdown_reference_report(
        source_root=tmp_path,
        relative_paths=[Path("alpha.md")],
        url_index_entries={
            "https://example.org/article": ReferenceUrlIndexEntry(
                url="https://example.org/article",
                last_checked_at="2026-05-31T10:00:00Z",
                http_status_code=200,
                reason_phrase="OK",
                content_type="text/html",
                filename="article",
                html_title="Example article",
                html_excerpt="First line of preview.\nSecond line of preview.",
            )
        },
    )

    assert report == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Bob](https://example.org/article) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/article\n\n"
        "- Status: 200 OK\n"
        "- Last checked: 2026-05-31T10:00:00Z\n"
        "- HTML Title: Example article\n"
        "- Content-Type: text/html\n"
        "- Filename: article\n"
        "```text\n"
        "First line of preview.\n"
        "Second line of preview.\n"
        "```\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n"
    )


def test_render_tree_markdown_reference_report_excludes_relative_links_from_cross_reference(
    tmp_path: Path,
) -> None:
    (tmp_path / "alpha.md").write_text(
        "# Sources\n\nSee [Local](./appendix.md).\n\nSee [Bob](https://example.org/bob).\n",
        encoding="utf-8",
    )

    report = render_tree_markdown_reference_report(
        source_root=tmp_path,
        relative_paths=[Path("alpha.md")],
    )

    assert report == (
        "# Markdown Reference Tree Index\n\n"
        "## alpha.md\n\n"
        "- [Local](./appendix.md) [Sources]\n"
        "- [Bob](https://example.org/bob) [Sources]\n\n"
        "## URL Cross Reference\n\n"
        "### https://example.org/bob\n\n"
        "References:\n"
        "- alpha.md [Sources] Bob\n"
    )