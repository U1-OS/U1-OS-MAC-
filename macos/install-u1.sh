#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
INSTALL=false
REPLACE=false
PERSONAL=false
for option in "$@"; do
  case "$option" in
    --install) INSTALL=true ;;
    --replace-desktop) REPLACE=true ;;
    --with-personal-deps) PERSONAL=true ;;
    *) printf 'Usage: bash macos/install-u1.sh [--with-personal-deps] [--install [--replace-desktop]]\n' >&2; exit 2 ;;
  esac
done
if [ "$REPLACE" = true ] && [ "$INSTALL" != true ]; then
  printf 'Replacement also requires --install.\n' >&2; exit 2
fi
if [ "$INSTALL" = true ] && [ "$REPLACE" != true ] && { [ -e "$HOME/Desktop/U1 OS.app" ] || [ -L "$HOME/Desktop/U1 OS.app" ]; }; then
  printf 'Desktop app already exists. Review the local build first; explicit --replace-desktop is required.\n' >&2
  exit 2
fi
if [ "$PERSONAL" = true ]; then /bin/bash "$ROOT/macos/bootstrap-personal.sh"; fi
/bin/bash "$ROOT/macos/build-desktop.sh"
if [ "$INSTALL" = true ]; then
  ARGS=(install "$ROOT/dist/U1 OS.app" "$HOME/Desktop")
  if [ "$REPLACE" = true ]; then ARGS+=(--replace-desktop); fi
  /usr/bin/python3 -B "$ROOT/macos/release_support.py" "${ARGS[@]}"
fi
