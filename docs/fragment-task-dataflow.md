# Fragment Task Dataflow

## Purpose

This note captures a historical workflow evolution that was proposed after the document-level fragment length report slice.

It is kept as design context only.
It does not describe the current supported command surface.

The original goal was to keep the same high-level Markdown summary scenario, but change the execution model:

1. extract fragments from one Markdown document
2. create one independent task per fragment
3. create one final merge task per document
4. assemble the final document-level output from the ordered fragment results

This was the first slice where the workflow would become a real dataflow pipeline instead of a pure file-by-file transformation.

## Why This Direction Fits The Existing Kernel

At the time of this proposal, the kernel already had most of the infrastructure needed:

- stable task identities
- persisted task records in JSON
- parent tasks that discover and create child tasks
- task revalidation
- sequential orchestration until the root task is resolved

The main missing capability was not scheduling.
The main missing capability was typed data exchange between tasks.

That is still a modest extension if we keep it explicit.

## Core Design Choice

The important rule should be:

- one task may depend on another task's published result
- that dependency should go through persisted task records
- the exchanged data should be modeled explicitly, not as ad hoc dictionary blobs

In practice, this means the workflow should not treat task JSON files as informal scratch files.
Instead, each task record should expose two different concerns:

- a human-oriented outcome message
- a machine-oriented result payload

## Recommended Result Model

At the time of this note, `TaskOutcome` was useful for status reporting, but too small for dataflow.

Today it contains:

- `message`
- `created_task_keys`
- `error`

For that next slice, the clean direction was to extend the outcome with a typed result payload.

Example direction:

```json
{
  "message": "Fragment processed.",
  "created_task_keys": [],
  "result": {
    "kind": "processed_fragment",
    "fragment_index": 3,
    "rendered_text": "- Paragraph under Introduction -> 148"
  }
}
```

The important design point is not the exact field names.
The important point is that the payload is a first-class modeled result.

That keeps the JSON records readable while also making them usable as workflow data.

## Why `result` In The Outcome Is Better Than A Separate Generic Store For Now

At that stage, keeping task output data inside the task record was a good fit.

Reasons:

- the project is still in a teaching phase
- one JSON file per task remains easy to inspect
- task output belongs conceptually to task execution
- we do not need a second persistence abstraction yet

Creating a separate generic artifact or payload store now would likely add more indirection than value.

So yes: adding fields in the task JSON is the right direction.
But it should be done through explicit domain models, not by sprinkling arbitrary keys into free-form dictionaries.

## Proposed Task Shapes

These task shapes are historical. They describe a removed intermediate slice and are no longer implemented.

### 1. `discover_document_fragments`

Purpose:

- parse one source Markdown document
- extract ordered fragments with heading context
- create one task per fragment
- create one merge task for the full document

Expected spec inputs:

- `relative_path`
- `source_digest`

Expected persisted children:

- zero or more `process_fragment` tasks
- one `merge_fragment_results` task

This task should stay responsible for planning, not for producing the final output itself.

### 2. `process_fragment`

Purpose:

- process one extracted fragment independently

Expected spec inputs:

- `document_relative_path`
- `fragment_index`
- `fragment_kind`
- `heading_path`
- `text`
- `fragment_digest`

The `fragment_digest` should be derived from the meaningful inputs of the fragment task.

That likely means at least:

- fragment text
- fragment kind
- heading path

If the future processing behavior depends on extra settings, those settings should also eventually participate in identity.

Expected result payload:

- processed text or rendered line to merge later
- enough metadata to confirm ordering and traceability

### 3. `merge_fragment_results`

Purpose:

- load the published results of the fragment tasks
- reassemble them in exact fragment order
- optionally add a header and footer
- write the final output document

Expected spec inputs:

- `document_relative_path`
- `source_digest`
- ordered `fragment_task_keys`
- optional header/footer settings

The merge task should not re-parse the source document to rebuild the result.
Its job is to consume upstream task outputs.

## Ordering Rule

The merge task must not rely on task key ordering.

The order should be explicit and durable.

The simplest rule is:

- discovery assigns each fragment a `fragment_index`
- fragment tasks persist that index
- merge receives the ordered list of child fragment task keys

That gives us a deterministic assembly order even if task keys are hash-based.

## Accessing One Task Result From Another Task

This is the only real architectural extension, but it is not a large one.

We already have `JsonTaskRepository.get(task_key)`.
So the concept already exists at the storage level.

What is missing is making it a normal application-level workflow capability.

Practical direction:

- handlers that need upstream data should receive the task repository
- the merge handler reads each referenced task record
- it validates that every required child task succeeded and published the expected result payload
- it builds the final output from those persisted results

That was enough to support a first dataflow slice.

## Revalidation Expectations

This slice would make revalidation more important.

The minimum expected rules are:

- `process_fragment` should be reusable if the exact same fragment task key already succeeded
- `merge_fragment_results` should become pending again if its output file is missing
- a succeeded merge task should also become waiting or pending again if one required fragment task is no longer succeeded
- `discover_document_fragments` should become waiting again if one child fragment task or the merge task is no longer satisfied

This stays aligned with the existing principle that success is not only a stored status.

## Why This Is Good Taste

Yes, this direction was of good taste if the scope stayed disciplined.

It fits the current architecture because:

- identities remain derived from meaningful inputs
- tasks stay passive data models
- handlers remain the place where effects happen
- the workflow becomes more data-oriented without needing concurrency yet
- expensive future fragment processing will benefit directly from reuse

It would become poor taste only if we introduced a vague "tasks can read arbitrary JSON from other tasks" convention without explicit result models and dependency rules.

## Recommended Implementation Bias

The first implementation was intended to stay narrower than the long-term translation case.

Recommended discipline:

- keep the current fragment extraction logic
- make `process_fragment` produce a very simple derived string first
- let `merge_fragment_results` assemble a Markdown report similar to the historical summary output of that slice
- add header and footer support only if it stays small and deterministic in this slice

This keeps the architectural step clear:

- task planning
- independent fragment execution
- persisted task results
- ordered merge from child task outputs

That would already have been a substantial and valuable evolution.