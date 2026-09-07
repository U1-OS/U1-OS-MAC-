#!/bin/bash
#
# U1 OS // Double-Click Launcher  (Wave 10)
# ---------------------------------------------------------------
# The bundle executable for "U1 OS.app". Boots the localhost
# server if it is not already up, waits for the port, then opens
# the command centre. Pure bash — no compiler, no dependencies.
#
# Runs live from the source checkout when it is still present, so
# a `git pull` is picked up without rebuilding the app; otherwise
# it falls back to the copy sealed inside the bundle.
#

BUNDLE_MACOS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_RES="$(cd "$BUNDLE_MACOS/../Resources" && pwd)"
PORT=8787
URL="http://127.0.0.1:$PORT"
LOG_DIR="$HOME/Library/Logs"
LOG="$LOG_DIR/U1-OS.log"
mkdir -p "$LOG_DIR"

notify() {
  /usr/bin/osascript -e "display notification \"$2\" with title \"U1 OS\" subtitle \"$1\"" >/dev/null 2>&1
}
fail() {
  /usr/bin/osascript -e "display dialog \"$1\" with title \"U1 OS — Launch Failed\" buttons {\"OK\"} default button 1 with icon caution" >/dev/null 2>&1
  exit 1
}

# ---- 1. Locate the application payload -------------------------
APP_ROOT=""
if [ -f "$BUNDLE_RES/source_path" ]; then
  CANDIDATE="$(cat "$BUNDLE_RES/source_path")"
  [ -f "$CANDIDATE/server.py" ] && APP_ROOT="$CANDIDATE"
fi
# Common checkout locations, so a repo moved or cloned elsewhere still wins
if [ -z "$APP_ROOT" ]; then
  for c in "$HOME/Documents/GitHub/U1-OS-MAC-" \
           "$HOME/Documents/GitHub/U1 OS ( MAC )" \
           "$HOME/GitHub/U1-OS-MAC-" \
           "$HOME/Developer/U1-OS-MAC-"; do
    if [ -f "$c/server.py" ]; then APP_ROOT="$c"; break; fi
  done
fi
# Otherwise run fully standalone from the sealed copy inside the bundle
if [ -z "$APP_ROOT" ] && [ -f "$BUNDLE_RES/app/server.py" ]; then
  APP_ROOT="$BUNDLE_RES/app"
fi
[ -z "$APP_ROOT" ] && fail "Could not find the U1 OS application files. Rebuild the app with build_launcher_app.sh."

# ---- 2. Locate a usable Python 3 -------------------------------
PY=""
for c in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  [ -x "$c" ] && PY="$c" && break
done
[ -z "$PY" ] && PY="$(command -v python3 2>/dev/null)"
if [ -z "$PY" ]; then
  /usr/bin/osascript -e 'display dialog "U1 OS needs Python 3, which ships with the Xcode Command Line Tools.\n\nClick Install to set it up, then launch U1 OS again." with title "U1 OS — Python 3 Required" buttons {"Cancel","Install"} default button 2' >/dev/null 2>&1 \
    && /usr/bin/xcode-select --install >/dev/null 2>&1
  exit 1
fi

# ---- 3. Already running? Just surface it -----------------------
if /usr/bin/curl -s -m 2 -o /dev/null "$URL/"; then
  /usr/bin/open "$URL"
  notify "Already running" "Command centre reopened on port $PORT."
  exit 0
fi

# ---- 4. Boot the server ----------------------------------------
cd "$APP_ROOT" || fail "Cannot open the application directory:\n$APP_ROOT"
{
  echo ""
  echo "=============================================================="
  echo "U1 OS launch $(date '+%Y-%m-%d %H:%M:%S')  |  root: $APP_ROOT"
  echo "=============================================================="
} >> "$LOG"

nohup "$PY" server.py >> "$LOG" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$APP_ROOT/.command-center.pid" 2>/dev/null

# ---- 5. Wait for the port to answer ----------------------------
for i in $(seq 1 50); do
  if /usr/bin/curl -s -m 2 -o /dev/null "$URL/"; then
    /usr/bin/open "$URL"
    notify "Online" "Command centre running at 127.0.0.1:$PORT"
    exit 0
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  sleep 0.4
done

TAIL="$(tail -n 12 "$LOG" 2>/dev/null | sed 's/"/\\"/g')"
fail "The server did not come up on port $PORT.\n\nLast log lines:\n$TAIL\n\nFull log: $LOG"
