# Ideas, TODO, and bugs
Here I put ideas that emerge.

## managing LLM callls

- timeout of LLM call should be configurable via workspace.yaml
- Timeout exception in LLM call does break the system, it should be trapped
- In case of LLM technical exception (timeout) a way to retry should exist... maybe few retries (configurable in yaml), and anyway, if the command is relaunched, past failed job should be just forgotten, thus retried.
- the time of LLM call should be displayed
- maybe computing the average and why not variance of translation call should be computed

## task scheduling

- it seems the fragment translation is done in random order... maybe it should be better if the fragments that will be merged in a given file are treated first, before treating the fragments of another file...
- why not showing the count of various task by state before scheduling a task. it can simply be don by increasing or decreasing totals (don't count), when task are created of state changed.

## translation improvement

- why not configure a size in bytes of pre_context and post_context. the idea is to add preceding and following fragments to a pre and post context, until it is longer than the configured limit. then this context may be put in the task then in the prompt, to helm making better translation
- why not add a glossary in the workspace yaml, as a list of french:english. 

## references and bibliography

- generating a single index of URL, each only one, but followed with list of the labels and the context (file, headers). It should help to test each link manually, and then see where to correct it.
