# User Guide

## Purpose

Do My Work is a batch command-line tool for repository-scale document workflows.

It was created first to translate a repository of French Markdown articles into English.
The tool then expanded to cover the surrounding operational needs that appear in the same repositories:

- references and citations must stay inspectable
- supporting resources such as images, PDFs, or `.url` files must be copied consistently
- the generated output tree must be checked for missing files and unexpected leftovers

The CLI is organized around those workflows.

## Core model

The tool works with three main directories:

- `input_dir`: source repository tree to read from
- `output_dir`: generated tree to write to
- `data_dir`: internal state for persisted tasks, runs, and intermediate workflow data

Configuration follows this precedence order:

1. built-in defaults
2. YAML configuration file
3. command-line overrides

In practice, most users will keep a shared YAML file such as `config/workspace.yaml` and override paths only for one-off runs.

## Typical workflow

For a documentation repository, the common sequence is:

1. generate or refresh reference reports
2. translate selected documents
3. copy selected resources
4. run the spurious-file report to inspect missing or unexpected outputs

Not every repository needs every command on every run, but the commands are designed to work together around the same input and output trees.

## Global CLI usage

Show the command list:

```powershell
do-my-work --help
```

Most workflow commands accept the same path controls:

- `--config`: path to a YAML workspace configuration file
- `--input-dir`: override the configured input directory
- `--output-dir`: override the configured output directory
- `--data-dir`: override the configured data directory
- `--root`: restrict the run to a relative subtree under `input_dir`

When both YAML and command-line values are present, command-line values win.

## Commands

### `translate-document-tree`

Use this command to translate selected source documents through fragment-based tasks and a named translator profile.

Typical use:

```powershell
do-my-work translate-document-tree --config config/workspace.yaml
```

Why it exists:

- process a document tree consistently instead of translating files manually
- persist task state so runs can be observed and compared
- keep translation policy in YAML rather than scattering it in scripts

Main options:

- `--config`: load the workspace YAML file
- `--input-dir`: override the source tree
- `--output-dir`: override the generated tree
- `--data-dir`: override the workflow state directory
- `--root`: restrict translation to a subtree
- `--translator-profile`: choose the profile under `llm.translator` in YAML, default `technical`

Selection behavior:

- `.md` files follow `file_selection`
- non-`.md` files can also be translated when they are explicitly included by `file_selection`
- local `do-my-work.yaml` files can exclude files, switch profiles, and add hints through `translation` rules

Typical output:

- translated documents written under `output_dir`
- workflow summary in the CLI with task counts and LLM timings

### `reference-index-tree`

Use this command to generate Markdown reference reports from the selected input tree.

Typical use:

```powershell
do-my-work reference-index-tree --config config/workspace.yaml
```

Why it exists:

- inspect links and citations file by file
- build a root-level cross-reference for the whole tree
- make editorial review easier before or after translation

Generated files:

- one `.references.md` file next to each selected source document in the target tree
- one root-level `references.index.md` synthesis

Main options:

- `--config`: load the workspace YAML file
- `--input-dir`: override the source tree
- `--output-dir`: override the report destination tree
- `--data-dir`: override the workflow state directory
- `--root`: restrict indexing to a subtree
- `--report-to-input`: write the generated reports into `input_dir` instead of `output_dir`

Notes:

- this command indexes selected Markdown source documents
- generated reference reports are not re-indexed as new inputs when `--report-to-input` is used
- local `do-my-work.yaml` files can exclude files through `reference_index` rules

### `copy-resource-tree`

Use this command to copy selected non-generated resources from the input tree to the output tree.

Typical use:

```powershell
do-my-work copy-resource-tree --config config/workspace.yaml
```

Why it exists:

- keep assets aligned with translated content
- avoid manual copy steps for images, PDFs, URLs, or other support files
- make the output tree closer to a usable publication tree

Main options:

- `--config`: load the workspace YAML file
- `--input-dir`: override the source tree
- `--output-dir`: override the destination tree
- `--data-dir`: override the workflow state directory
- `--root`: restrict copying to a subtree

Selection behavior:

- resource files are selected through `resource_selection`
- local `do-my-work.yaml` files can exclude files through `resource_copy` rules

### `spurious-file-report`

Use this command to compare the output tree with what the tool expects from translation and resource-copy rules.

Typical use:

```powershell
do-my-work spurious-file-report --config config/workspace.yaml
```

Why it exists:

- detect outputs that should not be there anymore
- detect outputs that are expected but still missing
- distinguish likely translated outputs from copied resources in the report

What the report checks:

- expected translated outputs derived from `file_selection` and local translation rules
- expected copied resources derived from `resource_selection` and local resource-copy rules
- ignored output patterns from `spurious_detection` and local `spurious` rules

Main options:

- `--config`: load the workspace YAML file
- `--input-dir`: override the source tree used as the expectation baseline
- `--output-dir`: override the tree to inspect
- `--data-dir`: override the data directory used to ignore workflow state artifacts
- `--root`: restrict the comparison to a subtree
- `--report-to-input`: write `spurious-files.md` into `input_dir` instead of `output_dir`

Output:

- `spurious-files.md` with summary counts
- grouped sections for spurious translated files, spurious copied resources, and missing files

### `clean-tasks`

Use this command to remove persisted workflow task JSON files from `data_dir`.

Typical use:

```powershell
do-my-work clean-tasks --config config/workspace.yaml
```

Why it exists:

- clear stored task state when you want a cleaner local workspace
- remove stale task files during debugging or workflow evolution

Main options:

- `--config`: load the workspace YAML file
- `--data-dir`: override the directory that contains persisted task files

Output:

- the CLI prints the resolved `data_dir`
- the CLI prints the number of removed task files

### `compare-runs`

Use this command to compare two persisted workflow runs by their saved summaries.

Typical use:

```powershell
do-my-work compare-runs --config config/workspace.yaml
```

Why it exists:

- inspect how one run differs from another without reading raw JSON by hand
- compare execution volume, replay counts, failures, and LLM timing metrics
- understand the operational effect of a config or workflow change

Main options:

- `--config`: load the workspace YAML file
- `--data-dir`: override the directory that stores persisted run files
- `--older-run-id`: choose the older run explicitly
- `--newer-run-id`: choose the newer run explicitly
- `--request-kind`: restrict the comparison to one workflow type

Default behavior:

- if no run ids are provided, the command compares the latest run with the previous run of the same workflow kind
- if one explicit run id is provided without the other, the command fails

## Configuration overview

The most important workspace-level configuration areas are:

- `file_selection`: include or exclude documents for translation and reference indexing
- `resource_selection`: include or exclude resources for copying
- `spurious_detection`: include or exclude paths from the missing/spurious report
- `llm.translator`: translator profiles used by `translate-document-tree`

Local `do-my-work.yaml` files refine behavior inside subtrees.
Depending on the workflow, they can exclude files, override translator profiles, add translation hints, or exclude paths from copy and spurious detection.

For the detailed local rule format, see `docs/local-workflow-config.md`.

## Recommended operating habits

- keep a shared `config/workspace.yaml` committed with the repository
- use `--root` for targeted runs while validating a new slice of content
- inspect `do-my-work --help` and `<command> --help` after upgrading the tool
- update this document and `README.md` when commands, options, or workflow expectations evolve

That last point is intentional: the user documentation is part of the product surface and should evolve with the CLI.