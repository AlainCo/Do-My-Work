# Packaging Notes

## Purpose

This note documents a practical first packaging target for this project: a Windows `one-folder` bundle built with PyInstaller.

The goal of this slice is not to solve universal distribution yet.
The goal is to let another developer run the tool from `./dist/` on a second development machine and report packaging-specific issues.

## Recommendation

For this project, start with `one-folder`, not `one-file`.

Why:

- `one-folder` is usually easier to debug when a dependency is missing at runtime
- `one-folder` avoids the startup extraction overhead of `one-file`
- `one-folder` is less likely to trigger Windows antivirus or SmartScreen friction
- this project already expects external inputs, outputs, configs, and state directories, so a single self-extracting executable is not required for the first useful packaging slice

The remaining discussion for later is whether a true single-file executable is worth the tradeoffs.

## Current Feasibility

The project is a good candidate for a packaged CLI because:

- the entry point is explicit in `src/do_my_work/cli.py`
- the application is a console workflow tool, not a GUI app
- configuration and workflow data already live outside the Python package
- the dependency surface is packageable on Windows, even if some libraries make the bundle heavier

Expected cautions:

- packaging is platform-specific; build Windows binaries on Windows
- `trafilatura` and related dependencies may increase bundle size
- `pypdf` and parser dependencies should be validated with real commands, not just `--help`

## Build Environment

Use the project virtual environment on the packaging machine.

Install the project and PyInstaller:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install pyinstaller
```

## Build Script

For repeatable local builds, use the Windows helper script:

```powershell
.\scripts\build-one-folder.bat
```

Quick environment check without running the build:

```powershell
.\scripts\build-one-folder.bat --check
```

The script:

- resolves the repository root automatically
- uses the project virtual environment under `.venv`
- runs PyInstaller from that environment
- leaves the generated bundle under `./dist/do-my-work/`

## Build Command

Run the build from the repository root.

The script above is the preferred path.
The raw PyInstaller command is kept here for transparency and debugging.

```powershell
pyinstaller `
  --noconfirm `
  --clean `
  --name do-my-work `
  --console `
  --paths src `
  --collect-all trafilatura `
  src/do_my_work/cli.py
```

Expected output location:

- `./dist/do-my-work/do-my-work.exe`

This is intentional.
The packaged application should stay under `./dist/` rather than being copied into the repository root.

## What To Copy To Another Machine

For a first realistic developer-to-developer test, copy:

- the whole `./dist/do-my-work/` folder
- one workspace config file such as `config/workspace.yaml` or a dedicated test config
- a small input tree suitable for quick validation

Do not assume the target machine is a perfectly blank machine yet.
The first useful goal is a second development machine where collaborators can report packaging bugs without rebuilding locally.

## Suggested Validation On The Other Machine

From the copied folder, validate in this order:

1. `do-my-work.exe --help`
2. `do-my-work.exe translate-document-tree --help`
3. `do-my-work.exe reference-index-tree --help`
4. a small translation run with a known local config
5. a small reference-index run
6. `do-my-work.exe spurious-file-report --config ...`

If translation review is part of the expected workflow, also test:

1. `do-my-work.exe translate-document-tree --config ... --with-review`
2. opening the generated `*.review.html`

## Practical Notes

- keep `input_dir`, `output_dir`, and `data_dir` outside the packaged folder when possible
- prefer a small dedicated packaging test workspace before trying a large real repository
- if a dependency is missing at runtime, adjust the PyInstaller recipe instead of moving files manually into the built folder

## Deferred Question

After `one-folder` has been validated on another developer machine, the remaining discussion is:

- do we also want a `one-file` executable, despite larger startup cost and higher packaging friction?
