# Foundations

## Current vocabulary

We use `WorkspaceConfig` as the first stable configuration object for the batch application.

The choice of words is important in this project.
Glossary terms should be chosen carefully because they influence the domain model, the command names, the documentation, and the way future features are discussed.

- `input_dir`: source tree to read from.
- `output_dir`: generated tree to write to.
- `data_dir`: internal working area for state, queues, progress, and intermediate artifacts.

## Why `workspace`

`work config` would be understandable, but `workspace` is more explicit in English and better matches a directory-oriented batch tool.

It also scales well if we later add:

- scanning policies
- include or exclude rules
- output strategies
- YAML-driven workflows

## Configuration precedence

The rule is simple:

1. built-in defaults
2. YAML configuration file
3. command-line overrides

This gives developers a stable default experience while still allowing explicit one-off runs.