# Ollama In This Project

## Purpose

This note explains what Ollama means for this repository, how it relates to the translation workflow, and what to do on a machine where the real Ollama runtime is unavailable.

In our project, Ollama is the local LLM server used by translation profiles under `llm.translator` in the selected YAML config.
Do My Work sends translation requests to that HTTP server.

Internally, the application no longer treats this layer as Ollama-only: the translation client code is provider-aware, and the profile `api` field selects the concrete adapter.

The important point is that the repository does not hard-code one model or one prompt.
The workflow is configurable through YAML:

- the Ollama server URL
- the model name
- the system prompt
- the user prompt
- timeout and retry behavior

Today, the real target model can be something like `ministral-3:3b`, but the project configuration can also point to `ollama-mock` for tests.

## What Ollama Is Used For Here

For a newcomer, the simple mental model is:

- Do My Work decides which documents and fragments should be translated
- Ollama runs the local language model server
- the translation profile in YAML tells Do My Work which model and prompts to use

That means Ollama is not the workflow engine itself.
It is the LLM runtime behind the translation step.

## Real Ollama Or Mock Ollama

There are two practical modes in this repository.

### 1. Real Ollama

Use this when your machine is allowed to install and run Ollama.

- good for real translation experiments
- uses a real model such as `ministral-3:3b`
- slower and heavier than the mock

### 2. Mock Ollama

Use this when:

- you only want to test the CLI and workflow wiring
- you do not have Ollama installed
- Ollama is blocked on your corporate machine

The mock output is intentionally ugly and unrealistic.
That is normal.
Its purpose is only to test that the application can talk to an Ollama-like server and complete the workflow.

The same mock server now also exposes an OpenAI-compatible `POST /v1/chat/completions` endpoint.
That lets provider-specific client tests reuse the same deterministic behavior layer.

In this repository, the checked-in example config currently points to `ollama-mock`, which makes sense for development and enterprise-restricted environments.

## Installing Ollama

If your machine is allowed to use the real runtime, use the official installation instructions from the Ollama project:

- official download page: [Ollama download](https://ollama.com/download)

That page is the right reference for current installers and platform-specific instructions.

After installation, you normally start the Ollama server and make sure your configured model is available.
The exact model name remains your project choice through the selected config, for example `config/garrigueollama.yaml`.

## Launching The Mock Server

The mock server exists for development and tests.
It behaves like a very small fake Ollama server so the workflow can run without the real runtime.

Install the optional mock dependencies first:

```powershell
python -m pip install -e ".[mock-ollama]"
```

### Mock On Windows

```bat
scripts\start-ollama-mock.bat
```

### Mock On Linux Or Git Bash

```bash
./scripts/start-ollama-mock.sh
```

Both mock scripts also accept `--check` to print the repository root and the selected Python executable without launching the server.

Once the mock server is running, the default development config can talk to `http://127.0.0.1:11434` just like it would talk to a real local Ollama instance.

For deeper implementation notes about the mock itself, see `docs/ollama-mock-tooling.md`.

## Launching Ollama In Trace Mode

Trace mode is useful when you want to inspect what the Ollama server is doing or debug runtime behavior outside the application.

This repository includes two convenience scripts that set verbose Ollama environment variables and then run `ollama serve`.

### Trace On Windows

```bat
scripts\start-ollama-trace.bat
```

### Trace On Linux

```bash
./scripts/start-ollama-trace.sh
```

The scripts currently set:

- `OLLAMA_LOG=debug`
- `OLLAMA_VERBOSE=1`

Then they start:

- `ollama serve`

Use these scripts only on a machine where the real Ollama runtime is installed and allowed.

## Practical Recommendation For This Repository

For someone discovering the project, the simplest path is:

1. start the mock server
2. use `config/garrigueollama.yaml` for a real Ollama runtime, or another local config if you want to target the mock instead
3. run the CLI workflows against the mock
4. switch to a real Ollama profile only when you actually need model-based translation behavior

That path is especially appropriate when Ollama cannot be installed in the company environment.
