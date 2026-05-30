# Local Workflow Config

## Purpose

This document defines the first version of the local workflow configuration file used inside the source document tree.

The goal is to let a folder express business-oriented overrides close to the documents themselves, without replacing the workspace-level configuration.

V1 is intentionally narrow.

- local config can further exclude files from processing
- local config can override the translation profile used for matching Markdown files
- local config can add translation hints for matching Markdown files
- local config does not add new files that the workspace-level selection already excluded
- local config does not yet add glossary entries or prompt fragments

## File Name And Location

The file name is `do-my-work.yaml`.

It lives in the input/source tree, not in the generated output tree.

Any folder under `input_dir` may define its own `do-my-work.yaml`.
The effective policy for a document is computed from all matching local config files between `input_dir` and the document folder.

## V1 YAML Shape

```yaml
version: 1

translation:
  rules:
    - match: "stories/**/*.md"
      profile: literary
      hints: |
        Use a narrative tone.
        Keep metaphors vivid but readable.

    - match: "drafts/**/*.md"
      exclude: true

reference_index:
  rules:
    - match: "drafts/**/*.md"
      exclude: true
```

## Sections

`translation.rules[]`

- `match`: glob-like pattern relative to the folder containing this `do-my-work.yaml`
- `exclude`: optional boolean; when `true`, matching files are excluded from translation
- `profile`: optional translation profile name from `workspace.yaml`; when present, matching files use this profile instead of the default run profile
- `hints`: optional free text appended to the effective translation hints for matching files

`reference_index.rules[]`

- `match`: glob-like pattern relative to the folder containing this `do-my-work.yaml`
- `exclude`: optional boolean; when `true`, matching files are excluded from reference indexing

## Precedence Rules

The effective policy for one document follows these rules.

1. workspace-level file selection remains the base gatekeeper
2. local config may exclude more files, but may not re-include files excluded by the workspace
3. for translation, the CLI or root workflow profile is the default profile
4. matching local `profile` rules may override that default translation profile for one document
5. matching local `hints` rules are accumulated in application order, so broader folders can provide shared guidance and deeper folders can add document-family-specific hints
6. within one config file, `last matching rule wins` for scalar values like `exclude` and `profile`
7. across multiple `do-my-work.yaml` files, deeper folders override higher folders because configs are applied from `input_dir` down to the document folder

## Matching Scope

Patterns are evaluated relative to the folder that contains the `do-my-work.yaml` file.

Example:

- config file: `docs/do-my-work.yaml`
- document: `docs/stories/chapter-01.md`
- rule pattern seen by this config: `stories/**/*.md`

## Revalidation Behavior

The workflow root task identity includes a digest of the relevant `do-my-work.yaml` files.

This means that changing local workflow config causes discovery to run again on the next workflow execution, even if the root path and top-level workspace config did not change.

For translation workflows, the effective local hints also contribute to downstream task identity, so changing `hints` forces fragment translation and document merge tasks to be recreated for the affected documents.

## Prompt Integration

Translation hints are only useful if the selected translator profile prompt uses them.

The translator prompt may reference `${translation_hints}` the same way it already references `${input_fragment}`, `${pre_context}`, or `${post_context}`.

Example:

```yaml
llm:
  translator:
    literary:
      user_prompt: |
        ${translation_hints}

        ${input_fragment}
```

## Current Limits

V1 intentionally does not do the following.

- no local `include` rules
- no local glossary entries yet
- no local prompt fragments yet
- no local reference-index parameters beyond exclusion
- no automatic cleanup of previously generated output files that became excluded after an earlier run

Those can be added later once the base behavior is stable and easy to reason about.
