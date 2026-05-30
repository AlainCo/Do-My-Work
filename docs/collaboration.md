# Collaboration Notes

## Purpose

This document captures the practical rules that help us work efficiently together on this repository.

It is intentionally separate from the public-facing README.
The README should stay short and useful for someone discovering the project.
This document keeps the working habits, documentation expectations, and local environment notes that matter during implementation.

## Working Method

We continue step by step.

- each change should stay understandable for a Python beginner
- each step should remain professionally structured
- architecture discussions should happen before large implementation jumps
- important decisions should be written in `docs/` instead of staying only in chat
- executable checks should accompany new behavior whenever the slice is testable

## Documentation Split

The documentation has two main levels.

- `README.md`: project overview, quick setup, main commands, and links to deeper notes
- `docs/*.md`: working documents, architecture notes, decisions, and collaboration rules

Practical rule:

- if a note helps understand the project from the outside, it belongs in `README.md`
- if a note helps us design, implement, validate, or resume work, it belongs in `docs/`

## Ideas Backlog

`docs/ideas-todo.md` is the shared backlog for ideas, improvements, annoyances, and future discussions that appear during implementation.

Practical rule:

- add a point there when it is worth keeping, but not part of the current implementation slice
- keep the current task focused instead of expanding scope immediately because of a newly discovered idea
- when a point is treated, either remove it or move it to a clearly marked done/history area in the same document
- keep nearby points grouped together so the document stays usable as a project-management note rather than a chat dump

## Collaboration Expectations

The following practices are now part of the working agreement for this repository.

- keep adding focused automated tests when a new slice becomes executable
- keep the CLI `--help` text aligned with the actual commands and options
- update the relevant document in `docs/` when a design decision or working rule becomes durable
- record deferred ideas and future improvements in `docs/ideas-todo.md` when they should not interrupt the current slice
- note local environment quirks when they cost time more than once
- treat glossary and terminology choices as important design decisions, because names shape the domain model, the CLI, and the documentation
- keep business-oriented traces of the tasks that are executed, replayed, created, or left unchanged when that behavior matters for understanding the workflow

## Local Environment Notes

Current useful notes for this workstation:

- prefer `.venv\Scripts\python.exe -m pytest` on Windows to avoid using a different global Python than the project virtual environment
- PowerShell requires quotes around `".[dev]"` when running `python -m pip install -e "[dev]"` style extras; in this project the safe command is `python -m pip install -e ".[dev]"`
- `rg` is not currently available in the PowerShell PATH, so workspace search tools are often faster than shell search commands here
- Typer help is available with `python -m do_my_work.cli --help` and `python -m do_my_work.cli <command> --help`, which is useful for keeping docs aligned with the real CLI surface

## Current Validation Habits

The default validation sequence for small slices is:

1. run the focused tests for the changed behavior
2. run the broader `pytest` suite once the slice is stable
3. run `ruff check .`

This keeps feedback fast while still leaving the repository in a clean state.