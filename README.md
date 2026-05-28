# Do My Work

Batch application scaffold in modern Python, with a simple CLI entry point, validated YAML configuration, and room for future workflow orchestration.

## Goals

- keep the project easy to read and publish on GitHub
- stay close to Python standards
- separate orchestration, domain objects, and technical I/O
- start with a trivial `Hello World` while keeping the right structure

## Project layout

```text
src/do_my_work/
  cli.py                    # CLI entry point
  application/batch_runner.py
  domain/models.py
  infrastructure/config_loader.py
  shared/logging_config.py
tests/
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

## Run the Hello World batch

Without a config file:

```powershell
do-my-work hello
```

With the provided YAML example:

```powershell
do-my-work hello --config config/hello.yaml
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

Once the hello flow is stable, the natural next move is to add a real job configuration model, a repository for persisted JSON state, and a workflow service that scans `work/input/` and writes to `work/output/`.