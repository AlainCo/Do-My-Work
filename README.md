# Do My Work

Batch application scaffold in modern Python, with a simple CLI entry point, validated YAML configuration, and room for future workflow orchestration.

## Goals

- keep the project easy to read and publish on GitHub
- stay close to Python standards
- separate orchestration, domain objects, and technical I/O
- start with a trivial batch while keeping the right structure

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

## Why these files exist

- `pyproject.toml`: the central project file for metadata, dependencies, test config, and tooling.
- `.python-version`: documents the Python version used by the project.
- `src/`: the recommended layout for import safety and packaging hygiene.
- `cli.py`: your manual batch entry point.
- `application/`: use cases and orchestration.
- `domain/`: business models without file-system concerns.
- `infrastructure/`: YAML/JSON/filesystem/API adapters.
- `tests/`: executable documentation and regression safety.
- `docs/`: living project notes for the team.

## Foundational naming

The first durable configuration concept is called `WorkspaceConfig`.

- `workspace`: a clear English name for the set of working directories used by the batch.
- `input_dir`: where source documents live.
- `output_dir`: where generated files are written.
- `data_dir`: where the application stores state, work items, and intermediate artifacts.

This is deliberately broader and more reusable than `HelloJobConfig`. It can survive when the real workflow arrives.

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

## Run the batch scaffold

Without a config file:

```powershell
do-my-work hello
```

With the provided YAML example:

```powershell
do-my-work hello --config config/workspace.yaml
```

Override one or more directories on the command line:

```powershell
do-my-work hello --input-dir custom/input --output-dir custom/output --data-dir custom/data
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

## Next architectural step

Once the workspace flow is stable, the natural next move is to add a repository for persisted JSON state and a workflow service that scans `work/input/` and writes to `work/output/`.