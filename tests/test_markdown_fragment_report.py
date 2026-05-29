from pathlib import Path

from do_my_work.infrastructure.markdown_fragment_report import (
    extract_markdown_fragments,
)


def test_extract_markdown_fragments_keeps_heading_context_and_atomic_blocks(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text(
        """---
title: Sample
---

# Intro

Alpha beta.

- Item one

> Quoted text.

```python
print(\"hi\")
```

## Diagram

```mermaid
graph TD
A-->B
```
""",
        encoding="utf-8",
    )

    fragments = extract_markdown_fragments(source_file)

    assert [
        (fragment.fragment_kind, fragment.heading_path, fragment.text, fragment.length)
        for fragment in fragments
    ] == [
        ("heading", ["Intro"], "Intro", 5),
        ("paragraph", ["Intro"], "Alpha beta.", 11),
        ("list_item", ["Intro"], "Item one", 8),
        ("blockquote", ["Intro"], "Quoted text.", 12),
        ("code_block", ["Intro"], 'print("hi")', 11),
        ("heading", ["Intro", "Diagram"], "Diagram", 7),
        ("mermaid", ["Intro", "Diagram"], "graph TD\nA-->B", 14),
    ]
