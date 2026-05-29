# Project Direction

## Purpose

This project aims to become a Python tool able to apply complex processing to a tree of Markdown documents.

Long-term examples include:

- translating a complete document tree
- checking URLs
- validating citations
- enforcing naming and documentation conventions
- generating reports and derived artifacts

The target is not a one-shot script. The target is a shareable GitHub project with a clean architecture, explicit data, and progressive evolution.

## How We Work

The working rules for collaboration, tests, CLI help maintenance, and local environment notes now live in `docs/collaboration.md`.

At the direction level, the important point is that we keep advancing in small, teachable increments.

## Stable Vocabulary

The current durable concept is `WorkspaceConfig`.

- `input_dir`: source documents to inspect and process
- `output_dir`: generated documents and reports
- `data_dir`: internal state for workflow data, manifests, caches, indexes, and intermediate artifacts

These three directories define the working workspace of the application.

## Product Vision

The long-term workflow can be described like this:

1. a user asks for a high-level result, for example translating everything under `input_dir`
2. the system discovers the documents involved
3. the system expands that request into smaller work items and derived artifacts
4. the system executes those work items in the right order
5. the system stores enough structured data to understand what was done and what remains to do
6. the system assembles final outputs in `output_dir`

This is closer to a demand-driven workflow engine than to a static Makefile.

The important difference is that the system does not know every artifact in advance. Some artifacts are discovered or created while trying to satisfy the initial request.

## Current Step

The current step is to design a small build/workflow kernel.

The current agreed design note for this step is in `docs/workflow-kernel.md`.

This kernel should eventually support scenarios such as:

- discovering Markdown files to process
- splitting documents into paragraph fragments
- producing derived artifacts such as translated fragments
- reassembling full translated documents
- keeping workflow state in JSON files under `data_dir`

At this stage, the goal is not to implement the full engine immediately.

The goal is to choose a small, teachable first slice that introduces the right concepts without too much complexity.

## Proposed Direction For The Kernel

The most sensible progression is:

1. define the workflow data we want to persist in JSON
2. define a minimal internal model for work items and artifacts
3. implement discovery of source Markdown files from a user request
4. implement one simple transformation pipeline on a tiny example
5. add status tracking and incremental rebuild rules only after the first path works

This ordering keeps architecture aligned with the target while staying accessible.

## Data Orientation

For this project, `data_dir` should become the place where the workflow keeps structured knowledge.

Likely categories:

- source inventory: which Markdown files exist and what identity they have
- artifact inventory: which derived files or logical artifacts exist
- work items: requested or discovered operations to execute
- execution state: pending, running, done, failed
- lineage: which artifact was produced from which inputs

At the beginning, simple JSON files are a good fit because they are easy to inspect, version mentally, and debug.

## Architectural Style

The existing project structure already points in a healthy direction.

- `domain/`: vocabulary and core models
- `application/`: orchestration and use cases
- `infrastructure/`: filesystem, YAML, JSON, Markdown parsing, external services
- `tests/`: regression protection and executable examples
- `docs/`: living decisions and project guidance

The next architecture work should preserve this style.

In practice, that means the workflow kernel should first be modeled in the domain and application layers, with filesystem and JSON persistence kept behind infrastructure adapters.

## Decision Log Practice

To keep discussions useful over time, we should maintain two levels of documentation:

- `README.md` for project overview and entry points
- documents in `docs/` for decisions, direction, architecture notes, and working agreements

Recommended habit:

- when we agree on a project direction, record it in `docs/`
- when a decision changes how newcomers understand the project, reflect it in `README.md`
- when a choice is temporary, mark it as the current step instead of presenting it as final architecture

## Current Kernel Slice

The workflow kernel is now implemented far enough to support the two retained public commands.

The currently supported user-facing workflows are:

1. `reference-index-tree`: discover Markdown documents, extract inline links, write one `.references.md` report per source file, and synthesize one root `references.index.md`
2. `translate-document-tree`: discover Markdown documents, extract ordered fragments, translate them through a named LLM profile, and merge them back into translated Markdown documents

This means the codebase now includes:

- stable task key generation for the retained reference and translation task kinds
- JSON repositories for runs and tasks under `data_dir`
- task handlers for reference indexing and fragment translation
- a sequential workflow engine loop
- the two retained CLI commands

Earlier copy-tree and fragment-length-report slices remain documented in `docs/` as historical design and teaching context, but they are no longer part of the supported command surface.

## Next Discussion

The next useful discussion is now about how to keep extending the retained workflows without carrying historical teaching slices as if they were still active product behavior.

The current preferred directions are now:

- strengthening the retained translation workflow
- deciding the next useful automation around the reference index workflow
- simplifying the internal kernel now that older copy and fragment-length flows have been removed

Historical intermediate slices are still captured for context in:

- `docs/markdown-fragment-slice.md`
- `docs/fragment-task-dataflow.md`

The active workflow notes for the current product surface are:

- `docs/reference-index-slice.md`
- `docs/translation-llm-slice.md`

For future external LLM integration, the repository now also distinguishes between the real infrastructure client and a repository-local Ollama mock server used only for development and integration testing.

That tooling direction is captured in `docs/ollama-mock-tooling.md`.