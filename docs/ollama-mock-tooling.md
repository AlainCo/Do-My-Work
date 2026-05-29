# Ollama Mock Tooling

## Purpose

This note records how the project should host a mock Ollama server for local development and integration testing.

The purpose is not to ship a fake Ollama implementation as part of the product.
The purpose is to test our HTTP integration layer against a realistic server surface without requiring a local Ollama install.

## Position In The Repository

The separation should stay explicit.

- the real Ollama client belongs in `src/do_my_work/infrastructure/`
- the mock Ollama server belongs in `tests/support/`

That keeps the runtime application clean while still versioning the test tool with the codebase.

## Two-Layer Design

The mock server should stay split into two layers.

### 1. Behavior Layer

File:

- `tests/support/ollama_mock_behavior.py`

This layer contains pure Python behavior objects.

Responsibilities:

- decide how the mock model responds
- simulate latency when useful
- expose a small contract for `version`, `tags`, `generate`, and `chat`

This layer is where we can later introduce multiple mock personalities, for example:

- normal echo-like behavior
- incompetent translator behavior
- slow behavior
- failing behavior
- malformed payload behavior

### 2. HTTP Server Layer

File:

- `tests/support/ollama_mock_server.py`

This layer exposes the HTTP endpoints and delegates all response decisions to the behavior object.

Responsibilities:

- map requests to behavior calls
- validate request shapes
- return Ollama-like JSON payloads

## Installation

The mock server should not impose FastAPI on the base project environment.

Instead, it uses a dedicated optional dependency group:

```powershell
python -m pip install -e ".[mock-ollama]"
```

## Launching The Mock Server

Direct module launch:

```powershell
.venv\Scripts\python.exe -m tests.support.ollama_mock_server
```

Or with Uvicorn factory mode:

```powershell
.venv\Scripts\uvicorn.exe tests.support.ollama_mock_server:create_app --factory --host 127.0.0.1 --port 11434
```

The default port matches the usual Ollama port so the future client can point to a remote or mock server with minimal configuration changes.

## Current Scope

The first mock surface is intentionally small.

Implemented endpoint targets:

- `GET /api/version`
- `GET /api/tags`
- `POST /api/generate`
- `POST /api/chat`

That is enough to start validating the network adapter and the request and response plumbing.