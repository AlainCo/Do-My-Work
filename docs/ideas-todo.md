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
- [SOON] [TODISCUSS] why not increase the size of the fragment. I propose a mechanism with 2 limits
  - let's introduce a "max_total_text_bytes" that limit the total of pre,input and post.
  - and a "max_input_fragment_bytes" that is a harder limit for the input_fragment.
  - Note that those limit are not enforced for the first input fragment that we cannot reduce. the only question is if we add few more segments. 
  - it will not be simple, so I propose this algorithm:
    - the first segment is mandatory even if toobig.
    - first we compute the "remaining bytes", the max_total_text_bytes minus max_pre_context_bytes plus  max_post_context_bytes
    - we increase that size in 2 phases.
      - phase 1: when the pre_context is empty or smaller than the limit,  we can increase the input_fragment size limit by the unconsumed pre_context_size, and thus increase the "remaining bytes". This mean we have to compute the pre_context before increasing the budget.
        - anyway there will be a hardlimit with the max_input_fragment_bytes, that prevent to increase the budget too much, so the "remaining bytes" will be caped to "max_input_fragment_bytes"
      - phase 2: when the post context have reached the end of the document, we can incorporate all the post context as a fragment to translate. this mean we have to try to extend input_fragment as much as possible according to the updated "remaining bytes" (and anyway respect max_input_fragment_bytes), then try to extends the post_context size as usual (limited by max_post_context_bytes), and see if we reach the end of the document
        - if we have read the end, we may move the segments in the post_context into the input_fragment
        - anyway there will be a hardlimit with the max_input_fragment_bytes, that prevent to increase the size of the input_fragment too much, so if we have reached the end of the document, we may only partially integrate the post_context segments to the input_fragment as long as it does not get above max_input_fragment_bytes.
    - of course the used segments put inside the input_fragment, should not be sent again as input_fragment... they will be consumed.
- [LATER] generating a document that propose original and translated fragment, fragment by fragment, would be very useful to check the translation. Markdown seems unable to do that, maybe HTML with tables but first the markdown should be converted to HTML fragment. is there better solution ?

## references and bibliography

- [LATER] generating a single index of URL, each only one, but followed with list of the labels and the context (file, headers). It should help to test each link manually, and then see where to correct it.

## file selection

- [TODISCUSS] its should be possible to tell files, file pattern or folder to include or to exclude. it should be configured in the workspace yaml. for translation of references scan.
  - it should be possible to ask for some file, filepatterns, folders, to be mapped to a translation profile name. why not use the include/exclude mechanism in translation profiles too ?
    Someone proposed me this idea, it seems nice and flexible:
    🎯 **Concept**
    You define a list of ordered rules.  
    Each rule has:

    - **match** — a glob pattern targeting `.md` files  
    - **action** — `include` or `exclude`  
    - **overrides** — more specific rules that override the parent  

    The **most specific rule wins**.

    🧱 **Minimal YAML**

    ```yaml
    rules:
      - match: "docs/**/*.md"
        action: include

      - match: "docs/drafts/**/*.md"
        action: exclude
        overrides:
          - match: "docs/drafts/reviewed/**/*.md"
            action: include

      - match: "**/*.tmp.md"
        action: exclude
        overrides:
          - match: "keep/**/*.tmp.md"
            action: include
    ```

    🧠 **Intended behavior**

    - `docs/**/*.md` → **included**  
    - `docs/drafts/**/*.md` → **excluded**  
    - `docs/drafts/reviewed/**/*.md` → **re‑included**  
    - `**/*.tmp.md` → **excluded**  
    - `keep/**/*.tmp.md` → **re‑included**
- an idea could be to add customization yaml in the target folder, to control few things.
  - the files to exclude (don't oppose with restriction at the workspace level, but add more locally)
  - some hints to add to the translator, glossary, corrections, warnings, specific to files or folder.