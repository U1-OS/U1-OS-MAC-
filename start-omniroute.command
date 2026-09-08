#!/bin/zsh
set -eu
cd "${0:A:h}"
umask 077
RUNTIME="$PWD/.runtime/omniroute"
NODE="/usr/local/bin/node"
if [[ ! -f "$RUNTIME/node_modules/omniroute/bin/omniroute.mjs" ]]; then
  printf 'OmniRoute is not installed in this workspace runtime.\n' >&2
  exit 1
fi
if /usr/sbin/lsof -nP -iTCP:20128 -sTCP:LISTEN >/dev/null 2>&1; then
  printf 'Port 20128 is already in use. No process was replaced.\n'
  exit 0
fi
mkdir -p "$RUNTIME/private" "$RUNTIME/data"
if [[ ! -f "$RUNTIME/private/local.env" ]]; then
  {
    printf 'JWT_SECRET=%s\n' "$(/usr/bin/openssl rand -hex 48)"
    printf 'API_KEY_SECRET=%s\n' "$(/usr/bin/openssl rand -hex 32)"
    printf 'INITIAL_PASSWORD=%s\n' "$(/usr/bin/openssl rand -hex 16)"
    printf 'OMNIROUTE_WS_BRIDGE_SECRET=%s\n' "$(/usr/bin/openssl rand -hex 32)"
  } > "$RUNTIME/private/local.env"
fi
set -a
source "$RUNTIME/private/local.env"
set +a
export DATA_DIR="$RUNTIME/data"
export OMNIROUTE_SERVER_HOST=127.0.0.1 HOST=127.0.0.1
export REQUIRE_API_KEY=true ALLOW_API_KEY_REVEAL=false
export OMNIROUTE_DISABLE_CREDENTIAL_HEALTH_CHECK=true
export NEXT_TELEMETRY_DISABLED=1
export PORT=20128 DASHBOARD_PORT=20128 API_PORT=20128
nohup "$NODE" "$RUNTIME/node_modules/omniroute/bin/omniroute.mjs" serve --port 20128 --no-open --no-tray --no-recovery > "$RUNTIME/private/server.log" 2>&1 < /dev/null &
printf '%s\n' "$!" > "$RUNTIME/private/launcher.pid"
printf 'OmniRoute launch requested on http://127.0.0.1:20128/\n'
printf 'Private startup credentials: .runtime/omniroute/private/local.env\n'
printf 'No provider accounts, subscriptions, or AI requests were connected automatically.\n'
