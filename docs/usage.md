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

## First run example

The example below shows a practical first pass on a repository of French articles and supporting assets.

1. Inspect the configured command surface.

```powershell
do-my-work --help
```

1. Generate reference reports for the current source tree.

```powershell
do-my-work reference-index-tree --config config/workspace.yaml
```

This produces one `.references.md` file per selected source document, one root-level `references.index.md` summary, and one root-level `references.index.yaml` sidecar for persistent URL metadata.

1. Translate the selected documents.

```powershell
do-my-work translate-document-tree --config config/workspace.yaml
```

This writes translated outputs under `output_dir` and prints a workflow summary with task counts and LLM timings.

1. Copy the selected non-Markdown resources.

```powershell
do-my-work copy-resource-tree --config config/workspace.yaml
```

This keeps images, PDFs, `.url` files, and other selected assets aligned with the generated tree.

1. Check the output tree for missing or unexpected files.

```powershell
do-my-work spurious-file-report --config config/workspace.yaml
```

This writes `spurious-files.md`, which helps detect outputs that are missing, stale, or outside the expected translation and copy rules.

1. If you changed selection rules or local config during experimentation, clean persisted tasks before a fresh rerun.

```powershell
do-my-work clean-tasks --config config/workspace.yaml
```

That sequence gives a clear first operational loop: inspect references, translate, copy assets, then verify the generated tree.

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
- `--with-review`: also generate an HTML review document showing each translated chunk side by side with its source chunk

Selection behavior:

- `.md` files follow `file_selection`
- non-`.md` files can also be translated when they are explicitly included by `file_selection`
- local `do-my-work.yaml` files can exclude files, switch profiles, and add hints through `translation` rules

Typical output:

- translated documents written under `output_dir`
- optional `*.review.html` files written next to translated documents when `--with-review` is enabled
- workflow summary in the CLI with task counts and LLM timings

Translation review behavior:

- the review document is an HTML file laid out in two columns, one chunk pair per row
- the chunks are the same translation units that were sent to the model, which may contain more than one atomic Markdown fragment when chunk grouping is enabled
- `workspace.yaml` can define `translation_review.translated_first: true` when you want the translated column shown before the original column

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
- one root-level `references.index.yaml` sidecar storing per-URL metadata and manual review fields

Main options:

- `--config`: load the workspace YAML file
- `--input-dir`: override the source tree
- `--output-dir`: override the report destination tree
- `--data-dir`: override the workflow state directory
- `--root`: restrict indexing to a subtree
- `--report-to-input`: write the generated reports into `input_dir` instead of `output_dir`
- `--check-urls`: perform an HTTP check for each unique referenced URL and add status information to the root URL cross reference

Notes:

- this command indexes selected Markdown source documents
- `workspace.yaml` can define `reference_index.max_pdf_bytes` to cap how much PDF content the URL checker is allowed to download and inspect for metadata and first-page text
- `workspace.yaml` can also define `reference_index.preview_max_text_chars` and `reference_index.preview_max_lines` to bound the HTML and PDF plain-text previews rendered into `references.index.md`
- generated reference reports are not re-indexed as new inputs when `--report-to-input` is used
- local `do-my-work.yaml` files can exclude files through `reference_index` rules
- when `--check-urls` is enabled, the root `references.index.md` report adds the HTTP status, content type, and a probable filename for each checked URL
- `references.index.yaml` keeps the URL metadata across runs, including `skip_recheck`, `last_checked_at`, `doi`, and `unused`
- when a URL entry has `skip_recheck: true`, later `--check-urls` runs reuse the stored metadata instead of launching a new HTTP check for that URL
- when a checked URL is itself a DOI link such as `https://doi.org/...`, the checker stores that DOI automatically in `references.index.yaml`
- for HTML pages, the checker also tries to extract a DOI from page metadata first, then falls back to a simple DOI pattern found in the URL or fetched content when it is obvious
- when `doi` is set in `references.index.yaml`, whether manually or automatically, the Markdown report shows it as a clickable DOI link
- when a checked URL goes through one or more HTTP redirects, the checker stores the last observed `Location` target in `references.index.yaml` and shows it in the Markdown cross-reference
- for successful HTML responses, the checker now stores a bounded HTML title and a short plain-text preview excerpt in `references.index.yaml` and shows them in `references.index.md`
- for successful PDF responses, the checker now tries to store PDF metadata such as title, author, and subject, plus a bounded plain-text excerpt from the first page when the PDF contains embedded text, but only up to `reference_index.max_pdf_bytes`
- preview length is controlled separately from download size: `preview_max_text_chars` limits the amount of extracted text retained, and `preview_max_lines` limits how many wrapped lines are rendered in the report
- proxy configuration follows the usual environment variables such as `http_proxy` and `https_proxy`
- HTTPS certificate validation is currently disabled for URL checks so the feature still works on machines without a configured trust store
- URL check errors such as TLS failures, timeouts, or HTTP error codes are reported in the cross-reference as normal results and do not make the workflow fail
- URL checks are intentionally simple in this slice: HTML extraction is bounded, prefers the raw HTML `title`, and uses `trafilatura` for a short plain-text preview without attempting full structured scraping

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

- `reference_index`: URL-check and preview extraction limits for the reference index workflow
- `translation_review`: layout preferences for optional HTML review documents generated by `translate-document-tree --with-review`
- `file_selection`: include or exclude documents for translation and reference indexing
- `resource_selection`: include or exclude resources for copying
- `spurious_detection`: include or exclude paths from the missing/spurious report
- `llm.translator`: translator profiles used by `translate-document-tree`

Local `do-my-work.yaml` files refine behavior inside subtrees.
Depending on the workflow, they can exclude files, override translator profiles, add translation hints, or exclude paths from copy and spurious detection.

For the detailed local rule format, see `docs/local-workflow-config.md`.

## Example `workspace.yaml`

The example below is a reasonable starting point for a repository of French articles, references, and supporting assets.

```yaml
input_dir: work/input
output_dir: work/output
data_dir: work/data

reference_index:
  max_pdf_bytes: 8388608
  preview_max_text_chars: 1200
  preview_max_lines: 5

translation_review:
  translated_first: false

file_selection:
  default_action: exclude
  rules:
    - match: "**/*.md"
      action: include
    - match: "**/*.txt"
      action: include
    - match: "**/*.references.md"
      action: exclude
    - match: "**/*.index.md"
      action: exclude

resource_selection:
  default_action: exclude
  rules:
    - match: "**/*.url"
      action: include
    - match: "**/*.jpeg"
      action: include
    - match: "**/*.jpg"
      action: include
    - match: "**/*.pdf"
      action: include

spurious_detection:
  default_action: include
  rules:
    - match: "manual/**/*"
      action: exclude
    - match: "**/*.review.html"
      action: exclude
    - match: "**/*.references.md"
      action: exclude
    - match: "**/*.index.md"
      action: exclude

llm:
  translator:
    technical:
      url: http://127.0.0.1:11434
      model: ollama-mock
      temperature: 0.0
      system_prompt: |
        You are a professional translator from french to english.
      user_prompt: |
        ===BEGIN PREVIOUS CONTEXT===
        ${pre_context}
        ===END PREVIOUS CONTEXT===

        ===BEGIN SOURCE TEXT===
        ${input_fragment}
        ===END SOURCE TEXT===

        ===BEGIN FOLLOWING CONTEXT===
        ${post_context}
        ===END FOLLOWING CONTEXT===
```

Why this example is useful:

- it sets explicit bounds for HTML and PDF previews in the reference index workflow
- it defines the default column order for optional translation review documents
- it translates both `.md` and explicitly included `.txt` inputs
- it excludes generated reference reports from the translation input set
- it excludes generated review HTML from the spurious-file report
- it copies common support files used in article repositories
- it keeps manually managed output areas out of the spurious-file report

Adapt the include and exclude rules to your repository rather than treating the example as a universal default.

## Example local `do-my-work.yaml`

Use a local `do-my-work.yaml` inside the input tree when one subtree needs stricter exclusions or a different translation policy than the rest of the repository.

Example:

```yaml
version: 1

translation:
  rules:
    - match: "drafts/**/*.md"
      exclude: true

    - match: "articles/**/*.md"
      profile: technical
      hints: |
        Keep the terminology consistent with earlier translated articles.
        Preserve citation markers and section structure.

reference_index:
  rules:
    - match: "drafts/**/*.md"
      exclude: true

resource_copy:
  rules:
    - match: "drafts/**/*.jpeg"
      exclude: true

spurious:
  rules:
    - match: "manual/**/*"
      exclude: true
```

Why this local example is useful:

- it keeps draft Markdown files out of translation and reference indexing
- it adds subtree-specific translation hints close to the documents that need them
- it prevents draft-only resources from being copied into the output tree
- it lets one subtree keep manually managed output files out of the spurious-file report

Scope reminder:

- the file name is always `do-my-work.yaml`
- it lives inside `input_dir`
- its patterns are evaluated relative to the folder that contains it
- local config can exclude more files or refine translation behavior, but it does not re-include files already excluded by the workspace-level config

## Troubleshooting

### A `.txt` file is not translated

For translation, non-`.md` files are not picked up implicitly.
They must be explicitly included by `file_selection`.

Example:

```yaml
file_selection:
  default_action: exclude
  rules:
    - match: "**/*.txt"
      action: include
```

If your `file_selection` excludes everything by default and only includes `.txt`, then only `.txt` files will be translated.
Add an explicit `.md` include rule as well if you want both kinds of files.

### `reference-index-tree --report-to-input` seems to create extra inputs

When `--report-to-input` is used, generated reference reports are written into `input_dir`.
The command is designed so those generated `.references.md` and `references.index.md` files are not re-indexed as new source documents.

As a general repository rule, it is still a good idea to keep generated report patterns excluded in `file_selection`.

### `spurious-file-report` shows missing files even though nothing looks wrong

This command reports both kinds of drift:

- files present in `output_dir` that are not expected anymore
- files expected from translation or resource copy that are still missing

So a nonzero `Missing output files` count is not necessarily a bug in the report.
It usually means that your selection rules say a file should exist in the output tree, but no workflow run has produced it yet.

### After changing YAML rules, the next run does not behave as expected

The workflow stores task state in `data_dir`.
In many cases, changing configuration is handled correctly by task identity and revalidation, but when you want a completely fresh rerun during debugging, clear the persisted task files first:

```powershell
do-my-work clean-tasks --config config/workspace.yaml
```

Then rerun the workflow command you care about.

### On Windows, the wrong Python or CLI may be used

If command resolution behaves unexpectedly, prefer the virtual environment Python explicitly:

```powershell
.\.venv\Scripts\python.exe -m do_my_work.cli --help
.\.venv\Scripts\python.exe -m pytest
```

This avoids accidentally using a different global Python than the one where the project is installed.

## Recommended operating habits

- keep a shared `config/workspace.yaml` committed with the repository
- use `--root` for targeted runs while validating a new slice of content
- inspect `do-my-work --help` and `<command> --help` after upgrading the tool
- update this document and `README.md` when commands, options, or workflow expectations evolve

That last point is intentional: the user documentation is part of the product surface and should evolve with the CLI.
