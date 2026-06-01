#!/bin/bash
set -euo pipefail

LLAMA_HOME_DIR="${LLAMA_HOME:-}"
LLAMA_NBCORE_N="${LLAMA_NBCORE:-}"


if [ -n "${LLAMA_HOME_DIR}" ] && [ -d "${LLAMA_HOME_DIR}" ]; then
  echo "Using llama server from LLAMA_HOME: ${LLAMA_HOME_DIR}"
else
  echo "LLAMA_HOME is not set or does not point to a valid directory. Please set LLAMA_HOME to the path of your llama server installation."
  exit 1
fi

if [ -n "${LLAMA_NBCORE_N}" ] && [ "${LLAMA_NBCORE_N}" -ge 1 ]; then
  echo "Using llama server from LLAMA_NBCORE: ${LLAMA_NBCORE}"
else
  echo "LLAMA_NBCORE is not set or is not positive. Please set LLAMA_NBCORE to the number of cores to use ."
  exit 1
fi

PORT="8000"
CTX_SIZE="8192"
MODEL="Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"

APP_OPTS=(
  -m "${LLAMA_HOME_DIR}/model/${MODEL}"
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
  -t "${LLAMA_NBCORE_N}"
  --batch-size 512
  --ubatch-size 512
  --mlock
)

exec "${LLAMA_HOME_DIR}/llama-server" \
  "${APP_OPTS[@]}" \
  "${NET_OPTS[@]}" \
  "${PERF_OPTS[@]}" \
  "${TRACE_OPTS[@]}"