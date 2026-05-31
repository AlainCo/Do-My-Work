# Ideas, TODO, and bugs

Here I put ideas that emerge.

This document is the shared backlog for ideas, improvements, annoyances, and deferred discussions that appear during implementation.

## Status vocabulary

Use the following markers when they help clarify priority or outcome:

- `[URGENT]`: should be treated soon because it blocks quality, reliability, or useful progress
- `[SOON]`: good candidate for a near-term implementation slice
- `[LATER]`: worth keeping, but intentionally deferred
- `[TODISCUSS]`: needs a design discussion before implementation
- `[DONE]`: treated and kept temporarily for traceability before cleanup
- `[ABANDONED]`: explicitly rejected, kept temporarily so the same idea is not reopened by accident

## Backlog hygiene

- when a point is treated, either remove it or move it to a short history section instead of leaving it mixed with active items
- when a point is no longer relevant, remove it rather than keeping stale backlog noise
- regularly group nearby points together and merge duplicates when they describe the same future change

## History / recently treated

- [DONE] We should put this document in our work methodology, saying that it's where we put ideas and improvement to be considered later
- [DONE] we should manage to clean this document when the point is treated, either removed, or in an history/done section
- [DONE] we may qualify points as DONE/ABANDONED/LATER/SOON/URGENT/TODISCUSS...
- [DONE] I've not observed trace/log for failed call (timeout), there should be one.
- [DONE] What if we stored the JSON data for the tasks in a folder named according to the task type, like discover_translate_document_fragments/ etc.?
- [DONE] we should have a command just to clean the tasks in the workspace
- [DONE] the hash of a translation task should depend on the content of the translation profile (except the url, max_retries, timeout, the max*bytes which are already in the data - in fact it remains, model, prompts, temperature), I imagine we will compute a hash of profile specification, so that all fragments that use a profile that has changed meaningfully, are retranslated next time.
- [DONE] we should add a header and footer (optional) to generated documents. best would be it is static not to cause spurious diff just for date of generation... if needed, user should just change the headers in the workspace yaml. my first test would be to add <!-- Translated by Do-My Work with ministrel-3:3g --> as header and footer.
- [DONE] workspace-level file selection now supports flat include/exclude rules in `workspace.yaml` for both translation and reference scan workflows.
- [DONE] larger translation inputs now support `max_total_text_bytes` and `max_input_fragment_bytes`, with contiguous fragment grouping and end-of-document absorption when the post-context reaches the end.
- [DONE] translate_fragment task keys now carry a stable per-document prefix so scheduler ordering keeps fragments from the same document together, allowing each output file to complete sooner.
- [DONE] workflow scheduling now logs active task counts by state before each task selection/execution, excluding unchanged tasks carried over from previous runs.
- [DONE] workflow run summaries now expose active task state counts in the CLI output, and LLM call logs include per-attempt elapsed time.
- [DONE] workflow run summaries now expose aggregated LLM timing stats (`attempt_count`, average, variance) for the current run.
- [DONE] `copy-resource-tree` now copies selected resources through the workflow engine, using workspace-level `resource_selection` rules and local `do-my-work.yaml` `resource_copy` exclusions.
- [ABANDONED] automatic cleanup of generated outputs when source documents or resources are renamed, moved, or deleted. This is too general and risky because it could destroy manually added output files; cleanup will remain manual.
- [DONE] local `do-my-work.yaml` config files under the source tree now support V1 business overrides: per-folder `exclude` rules for translation/reference workflows and per-folder translation `profile` overrides.
- [DONE] local `do-my-work.yaml` translation rules now support folder-scoped `hints`, exposed to prompts as `${translation_hints}`, and hints changes participate in translation task identity.
- [DONE] timeout of LLM call should be configurable via workspace.yaml
- [DONE]  Timeout exception in LLM call does break the system, it should be trapped
- [DONE] In case of LLM technical exception (timeout) a way to retry should exist... maybe few retries (configurable in yaml), and anyway, if the command is relaunched, past failed job should be just forgotten, thus retried.
- [DONE] the time of LLM call should be displayed
- [DONE] average and variance of translation call time are now computed for the current run summary from the LLM call attempts made during that run.
- [DONE] I noticed some calls take more than 300 seconds, error 500 server side (probably because connection is reset by client), but the retry works and it's faster after...
- [DONE] why not configure a size in bytes of pre_context and post_context. the idea is to add preceding and following fragments to a pre and post context, until it is longer than the configured limit. then this context may be put in the task then in the prompt, to helm making better translation
- [DONE] it should be possible to tell files, file pattern or folder to include or to exclude. it should be configured in the workspace yaml. for translation of references scan.
  - implemented as flat workspace-level rules with `default_action`, `match`, and `action`, using a simple `last matching rule wins` behavior

## managing LLM calls

## task scheduling

## translation improvement

- [LATER] [TODISCUSS] generating a document that propose original and translated fragment, fragment by fragment, would be very useful to check the translation. Markdown seems unable to do that, maybe HTML with tables but first the markdown should be converted to HTML fragment. is there better solution ?

## references and bibliography

- [SOON] [TODISCUSS] generating a single index of URL, each only one, but followed with list of the labels and the context (file, headers). It should help to test each link manually, and then see where to correct it.

## file selection

- [ABANDONED] it should be possible to ask for some file, filepatterns, folders, to be mapped to a translation profile name. why not use the include/exclude mechanism in translation profiles too ?
- [LATER] local `do-my-work.yaml` can later grow beyond `profile` and `hints` with glossary-like guidance, corrections, warnings, and other folder-specific business parameters.
- [SOON] we should check that it is possible to translate text files that are not "*.md", that file selections allows that.

## files copy
