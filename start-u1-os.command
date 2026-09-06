#!/bin/bash
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "$ROOT/launch_u1.py" "$@"
