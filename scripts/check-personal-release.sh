#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
if [ -n "${U1_RELEASE_PYTHON:-}" ]; then
  PYTHON="$U1_RELEASE_PYTHON"
elif [ -x "$ROOT/.runtime/bin/python3" ]; then
  PYTHON="$ROOT/.runtime/bin/python3"
else
  PYTHON=python3
fi
exec "$PYTHON" -I -B "$ROOT/macos/release_checks.py" "$@"
