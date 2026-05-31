from pathlib import Path
from collections import defaultdict

import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from do_my_work.domain.models import MarkdownReference, ReferenceUrlCheckResult


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
    url_check_results: dict[str, tuple[ReferenceUrlCheckResult | None, str | None, int | None]] | None = None,
) -> str:
    report_lines = ["# Markdown Reference Tree Index", ""]
    references_by_url: dict[str, list[tuple[str, str, str]]] = defaultdict(list)

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
                (
                    relative_path.as_posix(),
                    _format_heading_path(reference.heading_path),
                    reference.label,
                )
            )

    if references_by_url:
        report_lines.append("## URL Cross Reference")
        report_lines.append("")
        report_lines.extend(_render_url_cross_reference_lines(references_by_url, url_check_results))
        report_lines.append("")

    return "\n".join(report_lines)


def build_root_reference_index_path() -> Path:
    return Path("references.index.md")


def is_public_reference_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _render_reference_lines(references: list[MarkdownReference]) -> list[str]:
    return [
        f"- [{reference.label}]({reference.url}) [{_format_heading_path(reference.heading_path)}]"
        for reference in references
    ]


def _render_url_cross_reference_lines(
    references_by_url: dict[str, list[tuple[str, str, str]]],
    url_check_results: dict[str, tuple[ReferenceUrlCheckResult | None, str | None, int | None]] | None = None,
) -> list[str]:
    lines: list[str] = []

    for url in sorted(references_by_url):
        lines.append(f"### {url}")
        lines.append("")
        if url_check_results and url in url_check_results:
            result, error_category, http_status_code = url_check_results[url]
            lines.extend(_render_url_check_lines(result, error_category, http_status_code))
            lines.append("")
        for relative_path, heading_path, label in sorted(references_by_url[url]):
            lines.append(f"- {relative_path} [{heading_path}] {label}")
        lines.append("")

    if lines:
        lines.pop()

    return lines


def _render_url_check_lines(
    result: ReferenceUrlCheckResult | None,
    error_category: str | None,
    http_status_code: int | None,
) -> list[str]:
    lines: list[str] = []

    if http_status_code is not None:
        reason_phrase = None if result is None else result.reason_phrase
        if reason_phrase:
            lines.append(f"- Status: {http_status_code} {reason_phrase}")
        else:
            lines.append(f"- Status: {http_status_code}")
    elif error_category is not None:
        lines.append(f"- Status: {error_category}")

    if result is not None and result.content_type:
        lines.append(f"- Content-Type: {result.content_type}")
    if result is not None and result.filename:
        lines.append(f"- Filename: {result.filename}")
    if result is not None and result.final_url and result.final_url != result.url:
        lines.append(f"- Final URL: {result.final_url}")

    return lines


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