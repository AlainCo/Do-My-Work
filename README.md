# Do My Work

Batch application scaffold in modern Python, with a simple CLI entry point, validated YAML configuration, and room for future workflow orchestration.

## Documentation Map

- `README.md`: quick project overview and main entry points
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

## Current commands

Generate Markdown reference indexes with one `.references.md` file per input file and one root-level `references.index.md` synthesis:

```powershell
do-my-work reference-index-tree --input-dir work/input --output-dir work/output --data-dir work/data
```

Translate Markdown documents through fragment tasks with the `technical` translator profile from the YAML config:

```powershell
do-my-work translate-document-tree --config config/workspace.yaml
```

Inspect the current command surface:

```powershell
do-my-work --help
do-my-work reference-index-tree --help
do-my-work translate-document-tree --help
```

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