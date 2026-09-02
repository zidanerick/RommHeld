#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

VENV_DIR="${ROMMHELD_VENV:-.venv}"
PYTHON_BIN="${VENV_DIR}/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "RommHeld: creating local Python environment in ${VENV_DIR}..."
    python -m venv "$VENV_DIR"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "RommHeld: failed to create the Python environment." >&2
    exit 1
fi

# Keep project dependencies out of the system Python. This is important on
# Arch/CachyOS, where the system interpreter is externally managed.
"$PYTHON_BIN" -m pip install --disable-pip-version-check -q -r requirements.txt
exec "$PYTHON_BIN" launcher.py
