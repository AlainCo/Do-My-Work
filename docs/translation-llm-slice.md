# Translation LLM Slice

## Purpose

This note captures the first integration slice for fragment translation through an external LLM service.

The goal of this slice is not yet to complete the full fragment translation workflow.
The goal is to put in place the configuration and HTTP client foundations that the workflow will need.

## Why This Slice Comes First

The next workflow step will need to process fragments through a configurable translator profile.

Before adding new workflow task kinds, we need a stable answer for:

- how translator profiles are configured
- how prompts are rendered
- how the application talks to an Ollama-compatible HTTP endpoint
- how the same code can target a local server, a mock server, or a remote server

This makes the client and config slice a good prerequisite.

## Recommended Client Library

The preferred library for the first implementation is `httpx`.

Reasons:

- it is a common Python HTTP client
- it stays generic instead of hard-coding a local Ollama runtime assumption
- it works equally well with a real server, the project mock server, or a remote compatible endpoint
- it is easy to test with `httpx.MockTransport`

At this stage, a generic HTTP client is a better fit than a more opinionated Ollama-specific SDK.

## Proposed YAML Shape

The first configuration shape should stay simple and profile-oriented.

Example:

```yaml
llm:
  translator:
    technical:
      url: http://127.0.0.1:11434
      model: qwen2.5:7b
      credential:
      temperature: 0.1
      system_prompt: |
        You are a precise technical translator.
      user_prompt: |
        Translate the following fragment.
        ===BEGIN SOURCE TEXT===
        ${inputfragment}
        ===END SOURCE TEXT===

    emotional:
      url: http://127.0.0.1:11434
      model: qwen2.5:7b
      credential:
      temperature: 0.7
      system_prompt: |
        You are a more expressive translator.
      user_prompt: |
        Translate the following fragment.
        ===BEGIN SOURCE TEXT===
        ${inputfragment}
        ===END SOURCE TEXT===
```

This keeps the configuration explicit without becoming abstract too early.

## Prompt Templates

The first implementation should use simple named placeholders with Python `string.Template`.

Example placeholder:

- `${inputfragment}`

This is sufficient for the first translation slice and avoids introducing a heavier template engine too early.

If a required parameter is missing, prompt rendering should fail explicitly.

## First Client Responsibility

The initial client should be able to:

1. load one named translator profile
2. render the system and user prompts from named parameters
3. call `/api/chat` on the configured Ollama-compatible server
4. pass the configured model and temperature
5. optionally send a bearer credential when configured
6. return the assistant message content as the translated fragment text

That is enough to support the next workflow slice.

## Relationship To The Future Workflow

Once this slice is in place, the next translation workflow can reuse the same fragment-oriented dataflow introduced by the earlier fragment-reporting work:

1. discover Markdown documents to translate
2. extract ordered fragments
3. create one `translate_fragment` task per fragment
4. call the configured translator profile for each fragment
5. persist the translated fragment result in task outcome data
6. merge translated fragment results back into a document-level output

This preserves the same task-expansion and merge pattern, without keeping the old summary workflow as a supported product command.

## Current Implementation Scope

The current scope for this slice is now implemented for a first teaching path:

- typed translator profile configuration under `WorkspaceConfig`
- an Ollama-compatible HTTP client adapter
- prompt rendering with named placeholders
- a first fragment translation workflow command using the `technical` profile
- focused tests for configuration loading, request construction, and translation workflow behavior

The current translation workflow uses that earlier fragment pipeline shape at a simple level:

1. discover Markdown documents to translate
2. extract fragments
3. create one `translate_fragment` task per fragment
4. translate each reconstructed Markdown snippet through the configured profile
5. merge translated fragments in order with no header or footer

This is intentionally still modest.
The mock server output is simplistic, but the workflow mechanics are now in place.