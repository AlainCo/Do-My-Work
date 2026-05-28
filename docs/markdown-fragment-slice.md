# Markdown Fragment Slice

## Purpose

This note defines the next small slice after the current copy-based workflow kernel.

The goal is not translation yet.
The goal is to prove that we can parse Markdown documents, extract structured fragments with their heading context, and synthesize a derived Markdown report.

This is intentionally a teaching slice.
It should stay small, testable, and close to the future translation workflow.

## Current Status

The first executable version of this slice is now implemented.

Available command:

- `summary-document-tree`

Current behavior:

- discover Markdown documents under the requested subtree
- parse the document body with `markdown-it-py`
- ignore YAML front matter as document metadata using `python-frontmatter`
- extract headings and leaf blocks with parent heading context
- keep blockquotes, fenced code blocks, and Mermaid blocks as atomic fragments
- generate one Markdown fragment length report per source document in `output_dir`

## Chosen Libraries

For this slice, the current preferred libraries are:

- `markdown-it-py` for parsing Markdown into a usable structure
- `python-frontmatter` for reading YAML front matter when present

The front matter is treated as document metadata, not as part of the Markdown body itself.

## What We Want To Exercise

The next slice should demonstrate these abilities:

1. load a Markdown document
2. parse its block structure
3. identify the lowest-level blocks we want to treat as fragments
4. keep the parent heading context for each fragment
5. synthesize a Markdown report in `output_dir`

This is a good proxy for the later target:

- discover a document
- segment it into meaningful fragments
- process fragments one by one
- assemble a derived Markdown artifact

## Fragment Model For This Slice

For this iteration, we do not add configurable fragment selection yet.
That deserves its own later design step.

For now, we take the lowest-level blocks and attach the parent heading path.

The important consequence is:

- headings provide context
- headings are also reported as fragments themselves
- leaf blocks are the main units to inspect and measure

### Parent Heading Context

Each extracted fragment should carry the list of headings that contain it.

Example:

- heading path: `Introduction / Details`
- fragment type: `paragraph`
- fragment content: the paragraph text under that section

This gives us a structure much closer to future translation units than a plain line-by-line scan.

## Block Types For The First Markdown Slice

The current preferred fragment types are:

- `heading`
- `paragraph`
- `list_item`
- `blockquote`
- `code_block`
- `fence`

For this slice, some block kinds must stay atomic.
They should be treated as one object, not split into smaller translatable pieces.

That rule applies to:

- blockquotes
- fenced code blocks
- Mermaid blocks

In practice, a Mermaid block is expected to be recognized as a fenced code block with a language info string such as `mermaid`.

## What The Slice Produces

The derived artifact should be a Markdown report.

The report should stay intentionally simple:

- a heading
- the source document name
- a Markdown list describing fragment lengths

Example direction:

```markdown
# Fragment Length Report

Source: docs/example.md

- Heading: Introduction -> 12
- Paragraph under Introduction -> 148
- List item under Introduction -> 27
- Code block under Introduction / Example -> 96
```

The exact wording can still evolve.
The important point is that the output remains a Markdown document synthesized from parsed Markdown structure.

## What We Are Deliberately Not Solving Yet

This slice does not yet try to solve:

- configurable fragment selection from YAML or CLI
- translation rules per fragment type
- fragment identity persistence
- fragment inventories under `data_dir`
- reassembly of a translated document
- non-standard document concepts such as generic callouts or arbitrary "boxes"

Those are valid future topics, but they would widen the current step too early.

## Why This Slice Is Reasonable

This slice is more meaningful than file copying, but still modest enough to stay teachable.

It introduces:

- real Markdown parsing
- structural extraction instead of raw file copying
- context-aware fragments
- a derived Markdown artifact

It is therefore a good bridge between the toy workflow kernel and the later target of fragment-based translation and reassembly.
