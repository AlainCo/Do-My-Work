#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODEL="${REPO_ROOT}/model/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
LLAMA_HOME="${REPO_ROOT}/llama-b9442-bin-linux-x64"
PORT="8000"
CTX_SIZE="8192"

exec "${LLAMA_HOME}/llama-server" \
  -m "${MODEL}" \
  --host 127.0.0.1 \
  --port "${PORT}" \
  --ctx-size "${CTX_SIZE}" \
  -t 12 \
  --batch-size 512 \
  --ubatch-size 512 \
  --verbose \
  --mlock