# llama.cpp In This Project

## Purpose

This note explains how to use `llama.cpp` as the local LLM runtime for the translation workflow in this repository.

In the current Do My Work implementation, `llama.cpp` should be configured through the OpenAI-compatible provider mode:

- `api: openai`
- a base URL ending in `/v1`
- a model name matching the one exposed by the local `llama-server`

That works because `llama-server` exposes an OpenAI-compatible chat API.

## What To Install

You need two things:

1. a `llama.cpp` release that includes `llama-server`
2. a GGUF model file

Example sources:

- `llama.cpp` releases: <https://github.com/ggml-org/llama.cpp/releases>
- GGUF model example: <https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF>

Example model used successfully in this repository:

- `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`

## Example Windows Layout

One practical layout is:

```text
Do-My-Work/
  scripts/
    start-llamacpp.bat
  llama/
    llama-server.exe
    model/
        Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
```

The exact release folder name can differ depending on the downloaded archive.

## Example Linux Layout

One practical Linux layout is:

```text
Do-My-Work/
  scripts/
    start-llamacpp.sh
  llama/
    llama-server
    model/
        Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
```

Again, the release folder name can differ depending on the downloaded archive.

## Example Launch Scripts

This repository now contains a working example script at scripts/start-llamacpp.bat.

It also now contains a Linux or Git Bash variant at scripts/start-llamacpp.sh.

Both require an environment variable LLAMA_HOME pointing to the folder where llama-server binary exist, and assume there is a folder "model" with your model GGUF image.

Windows example:

```bat
@echo off
set PORT=8000
set CTXSIZE=8192
set MODEL=Ministral-3-3B-Instruct-2512-Q4_K_M.gguf

set APPOPTS=-m "%LLAMA_HOME%\model\%MODEL%" --ctx-size %CTXSIZE% 
set TRACEOPTS=
rem set TRACEOPTS=%TRACEOPTS% --verbose 
set TRACEOPTS=%TRACEOPTS% --metrics
set NETOPTS=--host 127.0.0.1 --port %PORT%
set PERFOPTS=-t 12  --batch-size 512 --ubatch-size 512  --mlock

@echo on
%LLAMA_HOME%\llama-server.exe %APPOPTS% %NETOPTS% %PERFOPTS% %TRACEOPTS%
@echo off
echo.
pause
```

Linux or Git Bash example:

```bash
#!/usr/bin/env bash
set -euo pipefail

PORT="8000"
CTX_SIZE="8192"
MODEL="Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"

APP_OPTS=(
  -m "${HERE}/model/${MODEL}"
  --ctx-size "${CTX_SIZE}"
)

TRACE_OPTS=(
  --metrics
)

NET_OPTS=(
  --host 127.0.0.1
  --port "${PORT}"
)

PERF_OPTS=(
  -t 12
  --batch-size 512
  --ubatch-size 512
  --mlock
)

exec "${LLAMA_HOME}/llama-server" \
  "${APP_OPTS[@]}" \
  "${NET_OPTS[@]}" \
  "${PERF_OPTS[@]}" \
  "${TRACE_OPTS[@]}"
```

What this does:

- loads the GGUF model file
- starts `llama-server` on `127.0.0.1:8000`
- exposes the OpenAI-compatible API used by Do My Work
- keeps a relatively large context window for fragment translation

On Linux, you will usually want to make the script executable first:

```bash
chmod +x scripts/start-llamacpp.sh
```

## YAML Configuration

For this repository, prefer the dedicated example profile in `config/garriguellamacpp.yaml`.

It already uses the OpenAI-compatible mode expected by `llama-server`.

Example:

```yaml
llm:
  translator:
    technical:
      api: openai
      url: http://127.0.0.1:8000/v1
      model: Ministral-3-3B-Instruct-2512-Q4_K_M
      timeout_seconds: 600.0
      max_retries: 2
      temperature: 0.0
      max_pre_context_bytes: 1200
      max_post_context_bytes: 1200
      max_input_fragment_bytes: 1200
      max_total_text_bytes: 3000
      system_prompt: |
        You are a professional translator from french to english.
      user_prompt: |
        ===BEGIN PREVIOUS CONTEXT===
        ${pre_context}
        ===END PREVIOUS CONTEXT===

        ===BEGIN SOURCE TEXT===
        ${input_fragment}
        ===END SOURCE TEXT===

        ===BEGIN FOLLOWING CONTEXT===
        ${post_context}
        ===END FOLLOWING CONTEXT===
```

Important details:

- `api` must be `openai`
- `url` should be the base URL ending in `/v1`
- the client then appends `/chat/completions`
- `credential` is usually unnecessary for a local `llama-server`
- `model` should match the model name exposed by the server

## Typical Workflow

1. start scripts/start-llamacpp.bat on Windows, or scripts/start-llamacpp.sh on Linux
2. keep the server window open
3. run the CLI with config/workspace.yaml

In practice, use `config/garriguellamacpp.yaml` for the checked-in `llama.cpp` example.

Example:

```powershell
do-my-work translate-document-tree --config config/garriguellamacpp.yaml
```

If you also want the side-by-side HTML output for manual review:

```powershell
do-my-work translate-document-tree --config config/garriguellamacpp.yaml --with-review
```

## Troubleshooting

### The profile works with the mock but not with `llama.cpp`

Check these first:

- the server is really running on `127.0.0.1:8000`
- the profile still has `api: openai`
- the base URL is `http://127.0.0.1:8000/v1`
- the configured model name matches the loaded model

The most common mistake is using `api: ollama` with `llama.cpp`.

### The requests time out

Increase `timeout_seconds` in the YAML profile.
For a local CPU run with a 3B model, a generous timeout such as `600.0` is reasonable.

### The model is too slow

That is usually a runtime issue, not a Do My Work issue.
The main levers are:

- smaller or more quantized GGUF model
- more CPU threads
- GPU-enabled `llama.cpp` build when available
- smaller context window
- smaller fragment/context byte limits in the YAML profile

## Practical Recommendation

For this repository, `llama.cpp` is a good option when:

- Ollama is not installed
- you want a local runtime under your control
- you already have a GGUF model that behaves well for translation

For fast CLI and workflow validation, the mock server is still the simplest path.
For actual translation quality checks, `llama.cpp` is a valid local alternative through the OpenAI-compatible mode.
