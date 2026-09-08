#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$ROOT/.runtime/bin/python3"
if [ ! -x "$PYTHON" ]; then PYTHON=/usr/bin/python3; fi
exec "$PYTHON" "$ROOT/utils/u1_launcher.py" open "$@"
