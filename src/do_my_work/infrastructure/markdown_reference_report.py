from pathlib import Path
from collections import defaultdict

import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from do_my_work.domain.models import (
    MarkdownReference,
    ReferenceUrlIndexEntry,
    ReferenceUrlOccurrence,
)


def extract_markdown_references(source_file: Path) -> list[MarkdownReference]:
    post = frontmatter.load(source_file)
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(post.content)
    heading_path: list[str] = []
    references: list[MarkdownReference] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]

        if token.type == "heading_open":
            close_index = _find_matching_close(tokens, index)
            heading_text = _collect_inline_content(tokens[index + 1 : close_index])
            heading_level = int(token.tag[1])
            heading_path = heading_path[: heading_level - 1]
            heading_path.append(heading_text)
            index = close_index + 1
            continue

        if token.type == "inline" and token.children:
            references.extend(_extract_inline_references(token.children, heading_path))

        index += 1

    return references


def render_markdown_reference_report(source_file: Path, source_root: Path) -> str:
    relative_source = source_file.relative_to(source_root).as_posix()
    references = extract_markdown_references(source_file)
    report_lines = ["# Markdown Reference Index", "", f"Source: {relative_source}", ""]

    report_lines.extend(_render_reference_lines(references))
    report_lines.append("")
    return "\n".join(report_lines)


def render_tree_markdown_reference_report(
    source_root: Path,
    relative_paths: list[Path],
    url_index_entries: dict[str, ReferenceUrlIndexEntry] | None = None,
) -> str:
    report_lines = ["# Markdown Reference Tree Index", ""]
    references_by_url: dict[str, list[ReferenceUrlOccurrence]] = defaultdict(list)

    for relative_path in relative_paths:
        source_file = source_root / relative_path
        references = extract_markdown_references(source_file)
        if not references:
            continue

        report_lines.append(f"## {relative_path.as_posix()}")
        report_lines.append("")
        report_lines.extend(_render_reference_lines(references))
        report_lines.append("")

        for reference in references:
            if not is_public_reference_url(reference.url):
                continue
            references_by_url[reference.url].append(
                ReferenceUrlOccurrence(
                    document_path=relative_path.as_posix(),
                    heading_path=list(reference.heading_path),
                    label=reference.label,
                )
            )

    if references_by_url:
        report_lines.append("## URL Cross Reference")
        report_lines.append("")
        report_lines.extend(_render_url_cross_reference_lines(references_by_url, url_index_entries))
        report_lines.append("")

    return "\n".join(report_lines)


def build_root_reference_index_path() -> Path:
    return Path("references.index.md")


def build_root_reference_index_yaml_path() -> Path:
    return Path("references.index.yaml")


def is_public_reference_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _render_reference_lines(references: list[MarkdownReference]) -> list[str]:
    return [
        f"- [{reference.label}]({reference.url}) [{_format_heading_path(reference.heading_path)}]"
        for reference in references
    ]


def _render_url_cross_reference_lines(
    references_by_url: dict[str, list[ReferenceUrlOccurrence]],
    url_index_entries: dict[str, ReferenceUrlIndexEntry] | None = None,
) -> list[str]:
    lines: list[str] = []

    for url in sorted(references_by_url):
        lines.append(f"### {url}")
        lines.append("")
        if url_index_entries and url in url_index_entries:
            metadata_lines = _render_url_check_lines(url_index_entries[url])
            if metadata_lines:
                lines.extend(metadata_lines)
                lines.append("")
        if references_by_url[url]:
            lines.append("References:")
        for occurrence in sorted(
            references_by_url[url],
            key=lambda item: (
                item.document_path,
                _format_heading_path(item.heading_path),
                item.label,
            ),
        ):
            lines.append(
                f"- {occurrence.document_path} [{_format_heading_path(occurrence.heading_path)}] {occurrence.label}"
            )
        lines.append("")

    if lines:
        lines.pop()

    return lines


def _render_url_check_lines(entry: ReferenceUrlIndexEntry) -> list[str]:
    lines: list[str] = []

    if entry.http_status_code is not None:
        if entry.reason_phrase:
            lines.append(f"- Status: {entry.http_status_code} {entry.reason_phrase}")
        else:
            lines.append(f"- Status: {entry.http_status_code}")
    elif entry.error_category is not None:
        lines.append(f"- Status: {entry.error_category}")

    if entry.last_checked_at:
        lines.append(f"- Last checked: {entry.last_checked_at}")
    if entry.doi.strip():
        normalized_doi = entry.doi.strip()
        lines.append(f"- DOI: [{normalized_doi}]({_build_doi_link(normalized_doi)})")
    if entry.html_title:
        lines.append(f"- HTML Title: {entry.html_title}")
    if entry.content_type:
        lines.append(f"- Content-Type: {entry.content_type}")
    if entry.filename:
        lines.append(f"- Filename: {entry.filename}")
    if entry.final_url and entry.final_url != entry.url:
        lines.append(f"- Final URL: {entry.final_url}")
    if entry.html_excerpt:
        lines.append("```text")
        lines.extend(entry.html_excerpt.splitlines())
        lines.append("```")

    return lines


def _build_doi_link(doi: str) -> str:
    normalized = doi.strip()
    if normalized.lower().startswith("https://doi.org/"):
        return normalized
    return f"https://doi.org/{normalized}"


def build_reference_report_relative_path(relative_path: Path) -> Path:
    return relative_path.with_name(f"{relative_path.stem}.references.md")


def _extract_inline_references(
    children: list[Token],
    heading_path: list[str],
) -> list[MarkdownReference]:
    references: list[MarkdownReference] = []
    active_url: str | None = None
    label_parts: list[str] = []

    for child in children:
        if child.type == "link_open":
            active_url = child.attrGet("href") or ""
            label_parts = []
            continue

        if child.type == "link_close":
            if active_url:
                references.append(
                    MarkdownReference(
                        heading_path=list(heading_path),
                        label="".join(label_parts).strip(),
                        url=active_url,
                    )
                )
            active_url = None
            label_parts = []
            continue

        if active_url is not None and child.type in {"text", "code_inline"}:
            label_parts.append(child.content)

    return references


def _collect_inline_content(tokens: list[Token]) -> str:
    parts = [
        token.content.strip()
        for token in tokens
        if token.type == "inline" and token.content.strip()
    ]
    return "\n".join(parts)


def _find_matching_close(tokens: list[Token], start_index: int) -> int:
    open_type = tokens[start_index].type
    close_type = f"{open_type[:-5]}_close"
    depth = 1

    for index in range(start_index + 1, len(tokens)):
        if tokens[index].type == open_type:
            depth += 1
        elif tokens[index].type == close_type:
            depth -= 1
            if depth == 0:
                return index

    raise ValueError(f"Could not find closing token for {open_type}")


def _format_heading_path(heading_path: list[str]) -> str:
    if not heading_path:
        return "root"
    return " / ".join(heading_path)