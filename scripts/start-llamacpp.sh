#!/bin/bash
set -euo pipefail

if [ -d "${LLAMA_HOME}" ]; then
  echo "Using llama server from LLAMA_HOME: ${LLAMA_HOME}"
else
  echo "LLAMA_HOME is not set or does not point to a valid directory. Please set LLAMA_HOME to the path of your llama server installation."
  exit 1
fi

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