# Markdown Reference Index Slice

## Purpose

This slice introduces a first useful report built from Markdown documents: a manual-checkable index of inline links.

The immediate goal is not citation normalization or URL validation.

The immediate goal is to extract links such as `[Label](https://example.org)` together with their heading context and render that information as Markdown.

## Why This Slice Matters

Compared to the earlier copy-tree and fragment-length examples, this report produces an output that is closer to a real editorial workflow.

It helps answer questions such as:

- which external references exist in a document
- under which section each reference appears
- which links should be checked manually before deeper automation is added

## Current Behavior

The workflow currently:

1. discovers Markdown documents under the requested subtree
2. parses inline Markdown links from each document
3. keeps the parent heading path for each extracted link
4. writes one `.references.md` report per source document

Example output shape:

```markdown
# Markdown Reference Index

Source: notes/example.md

- [Bob](https://example.org/bob) [Sources]
- [Alice](https://example.org/alice) [Sources / Further Reading]
```

## Deliberate Limits

For this first slice, the workflow does not yet:

- aggregate references across several documents into a global index
- validate URLs over HTTP
- deduplicate repeated links
- parse non-inline reference-style definitions

Those can come later once the current report is stable and genuinely useful.