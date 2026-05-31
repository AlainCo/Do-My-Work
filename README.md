# Do My Work

Do My Work is a batch CLI for repository-scale content workflows.
It was built first to help translate a repository of French Markdown articles into English, then grew to cover the practical problems around that job: keeping references visible, copying supporting resources, and spotting missing or unexpected output files.

The current workflow surface is designed for documentation-heavy repositories where repeatability matters more than ad hoc scripts.

## Why use it

- translate a selected document tree with YAML-driven rules and reproducible task state
- generate per-document and tree-wide reference indexes for citations and links
- copy selected non-Markdown resources alongside translated content
- report output files that are spurious or missing compared with the input tree and workflow rules

## Documentation Map

- `README.md`: quick project overview and main entry points
- `docs/usage.md`: user guide for the CLI, commands, options, and typical workflows
- `docs/foundations.md`: stable vocabulary and configuration rules
- `docs/project-direction.md`: product vision and current direction
- `docs/workflow-kernel.md`: design note for the toy workflow kernel
- `docs/markdown-fragment-slice.md`: design note for the first Markdown parsing and fragment reporting slice
- `docs/reference-index-slice.md`: design note for the Markdown reference indexing slice
- `docs/collaboration.md`: working method, documentation split, and local environment notes

## Project layout

```text
src/do_my_work/
  cli.py                    # CLI entry point
  application/batch_runner.py
  domain/models.py
  infrastructure/config_loader.py
  shared/logging_config.py
tests/
docs/
```

## Local setup with `venv` and `pip`

Create a local virtual environment:

```powershell
py -3.13 -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project and the developer tools:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

PowerShell note: the extra selector must be quoted. Without quotes, `[dev]` can be interpreted by the shell and `pip` may receive the wrong path.

For the project commands below, using the virtual environment Python explicitly is the safest option on this workstation:

```powershell
.\.venv\Scripts\python.exe -m do_my_work.cli --help
```

## Quick start

Inspect the CLI surface:

```powershell
do-my-work --help
```

Use the shared workspace config:

```powershell
do-my-work translate-document-tree --config config/workspace.yaml
```

Generate reference reports:

```powershell
do-my-work reference-index-tree --config config/workspace.yaml
```

Copy selected resources:

```powershell
do-my-work copy-resource-tree --config config/workspace.yaml
```

Check for missing or unexpected outputs:

```powershell
do-my-work spurious-file-report --config config/workspace.yaml
```

## Current commands

Generate Markdown reference indexes with one `.references.md` file per input file and one root-level `references.index.md` synthesis:

```powershell
do-my-work reference-index-tree --input-dir work/input --output-dir work/output --data-dir work/data
```

Add `--check-urls` when you also want the root URL cross reference to include HTTP status and content metadata for each unique referenced URL.

Translate Markdown documents through fragment tasks with the `technical` translator profile from the YAML config:

```powershell
do-my-work translate-document-tree --config config/workspace.yaml
```

Copy selected resources such as images, `.url` files, or source files from the input tree to the output tree:

```powershell
do-my-work copy-resource-tree --config config/workspace.yaml
```

Write a Markdown report at the output root listing files that are present in the output tree but are not expected from translation or resource copy:

```powershell
do-my-work spurious-file-report --config config/workspace.yaml
```

Inspect the current command surface:

```powershell
do-my-work --help
do-my-work copy-resource-tree --help
do-my-work reference-index-tree --help
do-my-work spurious-file-report --help
do-my-work translate-document-tree --help
```

For the full command guide, option reference, and workflow-oriented examples, see `docs/usage.md`.
If you want a practical onboarding path, start with the `First run example` section in `docs/usage.md`.

## FAQ

What is this tool for?

It is a batch CLI for document repositories, built first for translating French Markdown articles into English and then extended to handle references, copied resources, and output-tree validation.

Where should I start?

Start with `do-my-work --help`, then read the `First run example` section in `docs/usage.md`.

Where do I configure the workflows?

Use a shared workspace-level YAML file such as `config/workspace.yaml`, then add local `do-my-work.yaml` files inside the input tree when one subtree needs specific exclusions, profiles, or hints.

How do I understand missing or stale generated files?

Run `do-my-work spurious-file-report --config config/workspace.yaml` and inspect the generated `spurious-files.md` report.

## Run the tests

```powershell
pytest
```

## Lint and format checks

```powershell
ruff check .
ruff format --check .
```

For the current implementation direction and collaboration rules, use the documents under `docs/`.