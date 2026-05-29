from pathlib import Path

from do_my_work.infrastructure.markdown_reference_report import (
    extract_markdown_references,
    render_markdown_reference_report,
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