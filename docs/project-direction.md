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

The first persistence and execution slice of the toy workflow kernel is now implemented.

The current toy scenario is:

1. request: copy Markdown documents under `input_dir`
2. discovery: list Markdown documents under the requested subtree
3. persistence: store run and task state as JSON under `data_dir`
4. execution: copy files one by one into `output_dir`

This means the codebase now includes:

- stable task key generation for `discover_documents` and `copy_file`
- JSON repositories for runs and tasks under `data_dir`
- the first two task handlers
- a sequential workflow engine loop
- a small CLI command to launch the toy workflow

## Next Discussion

The next useful discussion is now about how to extend this first slice without breaking the step-by-step teaching approach.

Good candidates are:

- how much run summary data the CLI should print
- what failure and retry behavior we want in the persisted task model
- when to introduce artifact inventories versus keeping the task model central for a while