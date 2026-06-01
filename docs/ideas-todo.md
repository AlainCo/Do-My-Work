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
- [DONE] `spurious-file-report` now writes a Markdown report at the output root with files that are present in the output but are not expected from translation or resource copy.
  - it does not delete anything; it only reports
  - detection compares the output tree against files that could be translated from Markdown or copied as selected resources from the input
  - local `do-my-work.yaml` config is used through a `spurious.rules[]` exclusion section, analogous to translation and resource copy
  - workspace-level `spurious_detection` rules can exclude independently managed output folders or files from the report
  - the same report now also lists expected translated documents and copied resources that are missing from the output
- [DONE] `references.index.md` now ends with a URL cross-reference section: each URL appears once and is followed by the document path, heading hierarchy, and label text for each occurrence. It helps manual link review and correction.
- [DONE] `reference-index-tree --check-urls` now checks each unique referenced URL and enriches the root URL cross-reference with HTTP status, content type, and a probable filename. HTML title extraction remains a later slice.
- [DONE] `reference-index-tree` now also writes `references.index.yaml`, preserves manual URL metadata (`skip_recheck`, `doi`), reuses stored metadata when `skip_recheck: true`, carries `last_checked_at` into the Markdown report, and keeps unused URL entries marked as `unused` instead of deleting them.
- [DONE] DOI URLs such as `https://doi.org/...` are now recognized in the easy case: the checker stores the DOI automatically in `references.index.yaml`, while the Markdown cross-reference continues to show any defined DOI as a clickable link without overwriting a manual value.
- [DONE] HTML URL checks now extract a bounded `title` and a short plain-text preview excerpt, persist them in `references.index.yaml`, and render them in `references.index.md`. The current implementation prefers the raw HTML `title` and uses `trafilatura` for the preview text.
- [DONE] we should check that it is possible to translate text files that are not "*.md", that file selections allows that.
- [DONE]  why not search for doi in the scrapped text and list those found, and create links to them so the user can test them manually and replace his reference with the doi ?
- [DONE] successful PDF URL checks now extract bounded metadata and a first-page plain-text preview when possible, under the configured size limit
- [DONE] improve HTML page extraction beyond the current bounded title and plain-text excerpt
  - [ABANDONED] evaluate whether H1/H2/H3 add useful signal beyond the plain-text preview
  - [DONE] evaluate whether a dedicated extraction library is warranted for cleaner article text
  - [ABANDONED] if control becomes necessary, add an option like `--preview-urls`
  - [ABANDONED] if control becomes necessary, add an option like `--preview-urls-lines=NNN`
- [DONE] `translate-document-tree --with-review` now generates a side-by-side HTML review document per translated file, aligned by translation chunk rather than trying to force this into Markdown
- [DONE] translation review files can be generated on a later run with `--with-review` without redoing costly translation calls; changing `translation_review.translated_first` also re-renders the review without retranslating
- [DONE] local `do-my-work.yaml` translation rules can now override `translated_document_header` and `translated_document_footer` per file or subtree, so rare files such as translated `README.md` can carry specific automatic-translation notes or a different wrapper syntax for Markdown, text, or HTML outputs

## managing LLM calls

## task scheduling

## translation

## references and bibliography

## file selection

## files copy

## spurious file

## packaging

- [DONE] document the current `one-folder` packaging path with output kept under `./dist/`, so another developer machine can validate the bundle and report bugs
- [TODISCUSS] [SOON] after `one-folder` validation, is a true `one-file` executable worth the added startup cost and packaging friction ?

## command line, User interface and configuration

- [SOON] suppress useless options --translator-profile and clean useless code
- [TODISCUSS] [SOON] allow template variable in workspace yaml, so one can use environment variables
  - [SOON] one side effect is we need to allow empty values in workspace config, in some optional yaml fields like user/password or model, treating that as null/absent
- [LATER] why not propose a simple GUI/TEXTUI to launch commands, with chosen options

## documentation

- [TODISCUSS] [SOON] why not use the scripts (.bat .sh)  as doc as code for tooling, and reduce documentation and especially sample code which are redundant with the scripts. anyway we can keep general présentation and key points, but citing the scripts.
- [TODISCUSS] make full scripts and howto to translate, copy, check references, check spurious files, launching and using a fair model (ministral-3:8b), between my sibling projects  ../GNWT-garrigue-X (in french language) to ../GNWT-garrigue-X-en... maybe even add wget to download the models and the installations binaries... the target is beginners. it should be done first for windows... contributors may extend it for Linux or even Docker.
