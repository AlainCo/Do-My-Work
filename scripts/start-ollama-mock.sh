#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

WINDOWS_PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
POSIX_PYTHON="${REPO_ROOT}/.venv/bin/python"

if [[ -x "${POSIX_PYTHON}" ]]; then
  PYTHON_EXE="${POSIX_PYTHON}"
elif [[ -f "${WINDOWS_PYTHON}" ]]; then
  PYTHON_EXE="${WINDOWS_PYTHON}"
else
  echo "Could not find a project virtualenv Python in ${REPO_ROOT}/.venv." >&2
  echo "Install the project environment first, then run:" >&2
  echo "  python -m pip install -e \".[mock-ollama]\"" >&2
  exit 1
fi

if [[ "${1:-}" == "--check" ]]; then
  echo "Repo root: ${REPO_ROOT}"
  echo "Python executable: ${PYTHON_EXE}"
  exit 0
fi

cd "${REPO_ROOT}"
exec "${PYTHON_EXE}" -m tests.support.ollama_mock_server