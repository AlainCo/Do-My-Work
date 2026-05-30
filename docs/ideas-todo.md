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

## Project management

- we should regularly sort similar points together, or even merge them.

## managing LLM calls

- [DONE] timeout of LLM call should be configurable via workspace.yaml
- [DONE]  Timeout exception in LLM call does break the system, it should be trapped
- [DONE] In case of LLM technical exception (timeout) a way to retry should exist... maybe few retries (configurable in yaml), and anyway, if the command is relaunched, past failed job should be just forgotten, thus retried.
- the time of LLM call should be displayed
- maybe computing the average and why not variance of translation call should be computed
- I noticed some calls take more than 300 seconds, error 500 server side (probably because connection is reset by client), but the retry works and it's faster after...

## task scheduling

- [TODISCUSS] it seems the fragment translation is done in random order... maybe it should be better if the fragments that will be merged in a given file are treated first, before treating the fragments of another file...
  - [TODISCUSS] What if the ID of the fragment tasks, like translate_fragment, was prefixed with the hash of the document from which the fragments originate? This would help with sorting by document, and then the scheduler would list the tasks to be done in alphanumeric order, thus processing the fragments of the same document together.
- why not showing the count of various task by state before scheduling a task. it can simply be don by increasing or decreasing totals (don't count), when task are created of state changed. Note taht we should only count actives task, useful for this run.

## translation improvement

- [DONE] why not configure a size in bytes of pre_context and post_context. the idea is to add preceding and following fragments to a pre and post context, until it is longer than the configured limit. then this context may be put in the task then in the prompt, to helm making better translation
- [LATER] why not add a glossary in the workspace yaml, as a list of french:english or more generally translations hints.
- [LATER] why not control translation profile, glosssary, translation hints, file selection (add exclusion only, taking precedence over the workspace config) it in the target folder with yaml configuration
- [LATER] generating a document that propose original and translated fragment, fragment by fragment, would be very useful to check the translation. Markdown seems unable to do that, maybe HTML with tables but first the markdown should be converted to HTML fragment. is there better solution ?

## references and bibliography

- [LATER] generating a single index of URL, each only one, but followed with list of the labels and the context (file, headers). It should help to test each link manually, and then see where to correct it.

## file selection

- [DONE] its should be possible to tell files, file pattern or folder to include or to exclude. it should be configured in the workspace yaml. for translation of references scan.
  - implemented as flat workspace-level rules with `default_action`, `match`, and `action`, using a simple `last matching rule wins` behavior
- [LATER] it should be possible to ask for some file, filepatterns, folders, to be mapped to a translation profile name. why not use the include/exclude mechanism in translation profiles too ?
- [ABANDONED] nested `overrides` with "most specific rule wins" for the first version. a flat ordered rule list is enough for now and much simpler to reason about.
- [LATER] an idea could be to add customization yaml in the target folder, to control few things.
  - the files to exclude (don't oppose with restriction at the workspace level, but add more locally)
  - some hints to add to the translator, glossary, corrections, warnings, specific to files or folder.