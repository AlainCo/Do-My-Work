from pathlib import Path

import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from do_my_work.domain.models import MarkdownReference


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


def render_tree_markdown_reference_report(source_root: Path, relative_paths: list[Path]) -> str:
    report_lines = ["# Markdown Reference Tree Index", ""]

    for relative_path in relative_paths:
        source_file = source_root / relative_path
        report_lines.append(f"## {relative_path.as_posix()}")
        report_lines.append("")
        report_lines.extend(_render_reference_lines(extract_markdown_references(source_file)))
        report_lines.append("")

    return "\n".join(report_lines)


def build_root_reference_index_path() -> Path:
    return Path("references.index.md")


def _render_reference_lines(references: list[MarkdownReference]) -> list[str]:
    return [
        f"- [{reference.label}]({reference.url}) [{_format_heading_path(reference.heading_path)}]"
        for reference in references
    ]


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