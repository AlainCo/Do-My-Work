from pathlib import Path

import frontmatter
from markdown_it import MarkdownIt
from markdown_it.token import Token

from do_my_work.domain.models import MarkdownFragment


def extract_markdown_fragments(source_file: Path) -> list[MarkdownFragment]:
    post = frontmatter.load(source_file)
    parser = MarkdownIt("commonmark")
    tokens = parser.parse(post.content)
    heading_path: list[str] = []
    fragments: list[MarkdownFragment] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]

        if token.type == "heading_open":
            close_index = _find_matching_close(tokens, index)
            heading_text = _collect_inline_content(tokens[index + 1 : close_index])
            heading_level = int(token.tag[1])
            heading_path = heading_path[: heading_level - 1]
            heading_path.append(heading_text)
            fragments.append(
                MarkdownFragment(
                    fragment_kind="heading",
                    heading_path=list(heading_path),
                    text=heading_text,
                    length=len(heading_text),
                )
            )
            index = close_index + 1
            continue

        if token.type == "list_item_open":
            close_index = _find_matching_close(tokens, index)
            item_text = _collect_inline_content(tokens[index + 1 : close_index])
            if item_text:
                fragments.append(
                    MarkdownFragment(
                        fragment_kind="list_item",
                        heading_path=list(heading_path),
                        text=item_text,
                        length=len(item_text),
                    )
                )
            index = close_index + 1
            continue

        if token.type == "blockquote_open":
            close_index = _find_matching_close(tokens, index)
            blockquote_text = _collect_inline_content(tokens[index + 1 : close_index])
            if blockquote_text:
                fragments.append(
                    MarkdownFragment(
                        fragment_kind="blockquote",
                        heading_path=list(heading_path),
                        text=blockquote_text,
                        length=len(blockquote_text),
                    )
                )
            index = close_index + 1
            continue

        if token.type == "paragraph_open":
            close_index = _find_matching_close(tokens, index)
            paragraph_text = _collect_inline_content(tokens[index + 1 : close_index])
            if paragraph_text:
                fragments.append(
                    MarkdownFragment(
                        fragment_kind="paragraph",
                        heading_path=list(heading_path),
                        text=paragraph_text,
                        length=len(paragraph_text),
                    )
                )
            index = close_index + 1
            continue

        if token.type in {"code_block", "fence"}:
            fragment_kind = "code_block"
            if token.type == "fence" and token.info.strip().split(" ", maxsplit=1)[0] == "mermaid":
                fragment_kind = "mermaid"
            code_text = token.content.rstrip("\n")
            fragments.append(
                MarkdownFragment(
                    fragment_kind=fragment_kind,
                    heading_path=list(heading_path),
                    text=code_text,
                    length=len(code_text),
                )
            )

        index += 1

    return fragments


def render_fragment_length_report(source_file: Path, source_root: Path) -> str:
    relative_source = source_file.relative_to(source_root).as_posix()
    fragments = extract_markdown_fragments(source_file)
    report_lines = ["# Fragment Length Report", "", f"Source: {relative_source}", ""]

    for fragment in fragments:
        report_lines.append(
            f"- {fragment.fragment_kind} "
            f"[{_format_heading_path(fragment.heading_path)}] -> {fragment.length}"
        )

    report_lines.append("")
    return "\n".join(report_lines)


def build_summary_report_relative_path(relative_path: Path) -> Path:
    return relative_path.with_name(f"{relative_path.stem}.summary.md")


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