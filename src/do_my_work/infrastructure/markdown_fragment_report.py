from pathlib import Path
import html

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


def render_markdown_fragment(fragment: MarkdownFragment) -> str:
    if fragment.fragment_kind == "heading":
        heading_level = max(len(fragment.heading_path), 1)
        return f"{'#' * heading_level} {fragment.text}"

    if fragment.fragment_kind == "paragraph":
        return fragment.text

    if fragment.fragment_kind == "list_item":
        return f"- {fragment.text}"

    if fragment.fragment_kind == "blockquote":
        return "\n".join(f"> {line}" for line in fragment.text.splitlines())

    if fragment.fragment_kind == "code_block":
        return f"```\n{fragment.text}\n```"

    return f"```mermaid\n{fragment.text}\n```"


def render_translated_document(
    translated_fragments: list[str],
    header: str | None = None,
    footer: str | None = None,
) -> str:
    parts: list[str] = []
    if header:
        parts.append(header)
    parts.extend(translated_fragments)
    if footer:
        parts.append(footer)
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n"


def build_translation_review_path(relative_path: Path) -> Path:
        return relative_path.with_name(f"{relative_path.stem}.review.html")


def render_chunk_review_document(
        *,
        source_path: Path,
        source_fragments: list[str],
        translated_fragments: list[str],
        translated_first: bool = False,
) -> str:
        parser = MarkdownIt("commonmark")
        left_label = "Translated" if translated_first else "Original"
        right_label = "Original" if translated_first else "Translated"
        rows: list[str] = []

        for index, (source_chunk, translated_chunk) in enumerate(
                zip(source_fragments, translated_fragments, strict=True),
                start=1,
        ):
                left_markdown = translated_chunk if translated_first else source_chunk
                right_markdown = source_chunk if translated_first else translated_chunk
                rows.append(
                        "\n".join(
                                [
                                        '<section class="chunk-row">',
                                        (
                                                '  <div class="chunk-box"><div class="chunk-number">'
                                                f"Chunk {index}</div>{parser.render(left_markdown)}</div>"
                                        ),
                                        (
                                                '  <div class="chunk-box"><div class="chunk-number">'
                                                f"Chunk {index}</div>{parser.render(right_markdown)}</div>"
                                        ),
                                        "</section>",
                                ]
                        )
                )

        title = html.escape(source_path.as_posix())
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Translation review - {title}</title>
    <style>
        :root {{
            color-scheme: light;
            --page-bg: #f6f1e8;
            --panel-bg: #fffdf8;
            --panel-border: #b9aa8f;
            --muted: #6a6254;
            --text: #201c17;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: Georgia, "Times New Roman", serif;
            background: linear-gradient(180deg, #efe4d0 0%, var(--page-bg) 100%);
            color: var(--text);
        }}
        main {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }}
        h1 {{
            margin: 0 0 6px;
            font-size: 1.8rem;
        }}
        .path {{
            margin: 0 0 24px;
            color: var(--muted);
        }}
        .column-headings {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
            margin-bottom: 16px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--muted);
        }}
        .chunk-row {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
            margin-bottom: 16px;
        }}
        .chunk-box {{
            border: 1px solid var(--panel-border);
            background: var(--panel-bg);
            padding: 16px;
            overflow-wrap: anywhere;
        }}
        .chunk-number {{
            margin-bottom: 12px;
            color: var(--muted);
            font-size: 0.9rem;
            font-family: Arial, sans-serif;
        }}
        .chunk-box > :first-child {{ margin-top: 0; }}
        .chunk-box > :last-child {{ margin-bottom: 0; }}
        pre {{
            white-space: pre-wrap;
            background: #f1ebdf;
            padding: 12px;
            border: 1px solid #d9ccb5;
            overflow-x: auto;
        }}
        code {{ font-family: Consolas, "Courier New", monospace; }}
        @media (max-width: 900px) {{
            .column-headings,
            .chunk-row {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <main>
        <h1>Translation Review</h1>
        <p class="path">{title}</p>
        <div class="column-headings">
            <div>{left_label}</div>
            <div>{right_label}</div>
        </div>
        {rows}
    </main>
</body>
</html>
""".format(
                title=title,
                left_label=html.escape(left_label),
                right_label=html.escape(right_label),
                rows="\n".join(rows),
        )


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