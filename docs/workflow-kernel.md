# Workflow Kernel

## Purpose Of This Note

This document captures the first agreed design for a toy workflow kernel.

The immediate goal is not to build the final Markdown processing engine.
The immediate goal is to introduce the right architecture with a very small scenario.

## First Toy Scenario

The first scenario is intentionally simple:

1. the user asks to copy everything under `work/input`
2. the workflow engine discovers the files to process
3. the engine creates one unit task per file
4. each file is copied to the matching relative path under `work/output`
5. workflow state is persisted as JSON under `work/data`

This scenario is small, but it already exercises the architecture we want:

- a high-level request
- demand-driven task discovery
- persistent workflow state
- unit tasks with deterministic identity
- orchestration until no pending task remains

## Design Principles We Agreed On

### 1. Separate Runs From Tasks

A workflow run is not the same thing as a task.

- a run represents one invocation of the batch
- a task represents one concrete operation to be satisfied

This distinction matters because a run may be unique every time, while a task should usually have a stable identity derived from its meaningful inputs.

Because of that, we should not inject `now()` or a timestamp into task identity just to force uniqueness.

If we need uniqueness per launch, that belongs to the run object, not to the task object.

### 2. Keep Domain Models Passive

For this project, task models should describe data, not execute behavior.

That means:

- domain models represent validated state
- handlers or services perform effects such as listing files, hashing files, and copying files
- the workflow engine coordinates handlers and persistence

This is more teachable, easier to test, and simpler to serialize to JSON than putting `execute()` methods directly on each task model.

### 3. Prefer Stable Task Identity

Task identity should be derived from the inputs that actually matter for the computation.

Examples:

- for a file copy task: relative path plus source content digest
- for a future translation task: source fragment identity plus model or translation settings if they affect the output

This lets the workflow detect whether an already completed task result is still valid.

### 4. Start With One JSON Record Per Task

Conceptually, a task specification and a task outcome are different concerns.
But for the first implementation, they can live in the same persisted JSON record.

This keeps the storage model simple while still preserving the conceptual distinction between:

- what the task is
- what its current status is
- what happened when it ran

### 5. Introduce Only The Concepts Needed Today

The long-term architecture will probably include concepts such as artifacts, lineage graphs, fragment inventories, and incremental rebuild policies.

The first toy kernel does not need all of that.

For the first slice, the important concepts are:

- one run request
- a small number of task kinds
- task status
- task persistence
- one simple orchestration loop

## Proposed Vocabulary

The following names are the current preferred vocabulary.

- `RunRequest`: one batch invocation or requested high-level goal
- `TaskSpec`: the data that defines one task
- `TaskRecord`: the persisted record of one task, including status and outcome
- `TaskOutcome`: what a handler reports after attempting the task
- `TaskStatus`: pending, waiting, running, succeeded, failed
- `TaskHandler`: the component that knows how to process one task kind
- `WorkflowEngine`: the orchestrator that loops until the run is resolved

These names are intentionally ordinary and close to common backend or workflow terminology.

## First Task Kinds

The first toy kernel only needs two task kinds.

### `discover_files`

Purpose:

- inspect a subtree under `input_dir`
- identify files that must be copied
- create child `copy_file` tasks

Expected behavior:

- if matching child tasks already exist and are already satisfied, reuse them logically
- otherwise, persist newly needed child tasks
- remain in a waiting state until all child tasks succeed

### `copy_file`

Purpose:

- copy one source file from `input_dir` to the matching relative path in `output_dir`

Expected identity inputs:

- relative source path
- source content digest

Expected behavior:

- ensure the destination parent directory exists
- copy the file contents
- mark the task as succeeded if the operation completes

## Orchestration Model

The first engine can stay very simple and sequential.

Suggested loop:

1. create a `RunRequest`
2. create the root `discover_files` task for the requested subtree
3. load pending or waiting task records from `data_dir`
4. select a task that can make progress
5. dispatch it to its handler
6. persist the updated task record and any new child tasks
7. repeat until there is no pending or waiting work left

For the toy version, there is no need for concurrency, threads, or workers.

## Persistence Direction

The first JSON storage design should remain explicit and easy to inspect.

Suggested layout:

- `work/data/runs/` for run requests
- `work/data/tasks/` for task records

This is easier to understand than one large state file, and easier to evolve than a more abstract persistence layer too early.

## Suggested Shape Of The First Records

### Run request

```json
{
  "run_id": "2026-05-28T10:15:00Z",
  "request_kind": "copy_tree",
  "root": ".",
  "status": "running",
  "root_task_key": "task:discover:8f2d"
}
```

### Task record

```json
{
  "task_key": "task:copy:111a",
  "spec": {
    "kind": "copy_file",
    "relative_path": "testsubdir/subtest1.md",
    "source_digest": "sha256:abcd"
  },
  "status": "succeeded",
  "child_task_keys": [],
  "outcome": {
    "message": "File copied"
  }
}
```

These exact field names can still evolve, but this is the right level of explicitness.

## Why This Is A Good First Slice

This toy workflow is deliberately modest, but it forces us to put the main architecture in place:

- request versus task separation
- deterministic task identity
- handler-based execution
- persistent state in JSON
- orchestration driven by discovered work

Once this slice works, the next evolutions become much easier:

- filtering only Markdown files
- storing discovered file inventories
- splitting Markdown into fragments
- producing translated fragments
- reassembling full documents

## Current Implementation Status

The first domain models for the toy workflow kernel are now implemented.

Implemented in the codebase:

- `TaskStatus`
- `DiscoverFilesTaskSpec`
- `CopyFileTaskSpec`
- `TaskOutcome`
- `TaskRecord`
- `RunRequest`

What is intentionally not implemented yet:

- task key generation
- JSON repositories under `work/data`
- task handlers
- workflow engine loop
- CLI entry point for the toy workflow

## Next Technical Step

The next implementation step is to build the first persistence and execution slice around the models.

Recommended order:

1. add stable task key generation, especially for `copy_file`
2. add JSON repositories for runs and tasks under `work/data`
3. add the first two task handlers: `discover_files` and `copy_file`
4. add a sequential `WorkflowEngine` loop
5. expose the toy workflow through a small CLI command

The first milestone is simple: asking to copy all files from `input_dir` should create persistent task records, execute the needed copy tasks, and reproduce the directory tree under `output_dir`.