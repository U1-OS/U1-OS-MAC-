#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
PYTHON="$ROOT/.runtime/bin/python3"
if [ "$#" -ne 0 ] || [ ! -x "$PYTHON" ]; then
  printf 'Use this explicit optional bootstrap only with the existing .runtime Python environment.\n' >&2
  exit 2
fi
"$PYTHON" -I -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix else "Refusing to install packages into system Python")'
"$PYTHON" -I -m pip install --no-input --disable-pip-version-check --only-binary=:all: -r "$ROOT/requirements-personal.txt"
printf 'Personal dependencies installed in the existing local runtime; no app was installed or launched.\n'
