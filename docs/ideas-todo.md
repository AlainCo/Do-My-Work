# Ideas, TODO, and bugs

Here I put ideas that emerge.

## Project management

- [URGENT] We should put this document in our work methodology, saying that it's where we put ideas and improvement to be considered later
- we should manage to clean this document when the point is treated, either removed, or in an history/done section
- we may qualify points as DONE/ABANDONED/LATER/SOON/URGENT/TODISCUSS...
- we should regularly sort similar points together, or even merge them.

## managing LLM calls

- [DONE] timeout of LLM call should be configurable via workspace.yaml
- [DONE]  Timeout exception in LLM call does break the system, it should be trapped
- [DONE] In case of LLM technical exception (timeout) a way to retry should exist... maybe few retries (configurable in yaml), and anyway, if the command is relaunched, past failed job should be just forgotten, thus retried.
- the time of LLM call should be displayed
- maybe computing the average and why not variance of translation call should be computed

## task scheduling

- [TODISCUSS] it seems the fragment translation is done in random order... maybe it should be better if the fragments that will be merged in a given file are treated first, before treating the fragments of another file...
  - [TODISCUSS] What if the ID of the fragment tasks, like translate_fragment, was prefixed with the hash of the document from which the fragments originate? This would help with sorting by document, and then the scheduler would list the tasks to be done in alphanumeric order, thus processing the fragments of the same document together.
- why not showing the count of various task by state before scheduling a task. it can simply be don by increasing or decreasing totals (don't count), when task are created of state changed. Note taht we should only count actives task, useful for this run.
- [URGENT] the hash of a translation task should depend on the content of the translation profile (except the url, the max_retries and the timeout), I imagine we will compute a hash of profile specification, so that all fragments that use a profile that has changed meaningfully, are retranslated next time.
- [URGENT] What if we stored the JSON data for the tasks in a folder named according to the task type, like discover_translate_document_fragments/ etc.?

## translation improvement

- [DONE] why not configure a size in bytes of pre_context and post_context. the idea is to add preceding and following fragments to a pre and post context, until it is longer than the configured limit. then this context may be put in the task then in the prompt, to helm making better translation
- [LATER] why not add a glossary in the workspace yaml, as a list of french:english.
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

## references and bibliography

- [LATER] generating a single index of URL, each only one, but followed with list of the labels and the context (file, headers). It should help to test each link manually, and then see where to correct it.

## file selection

- [TODISCUSS] its should be possible to tell files, file pattern or folder to include or to exclude. it should be configured in the workspace yaml. for translation of references scan.
  - it should be possible to ask for some file, filepatterns, folders, to be mapped to a translation profile name. why not use the include/exclude mechanism in translation profiles too ?
