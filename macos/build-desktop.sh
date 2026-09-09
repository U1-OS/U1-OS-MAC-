#!/bin/bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
if [ "$#" -gt 0 ]; then
  printf 'Usage: bash macos/build-desktop.sh\n' >&2
  exit 2
fi
if [ "$(uname -s)" != Darwin ]; then
  printf 'A local macOS SDK and Swift compiler are required.\n' >&2
  exit 1
fi
[ ! -L "$ROOT/dist" ] || { printf 'Refusing a symlinked dist directory.\n' >&2; exit 1; }
mkdir -p "$ROOT/dist"
LOCK="$ROOT/dist/.u1-desktop-build.lock"
mkdir "$LOCK" || { printf 'Another build owns the lock; do not remove an active build lock.\n' >&2; exit 1; }
BUILD=""
cleanup() {
  if [ -n "$BUILD" ]; then rm -rf -- "$BUILD"; fi
  rmdir "$LOCK"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
BUILD="$(mktemp -d "$ROOT/dist/.u1-desktop-build.XXXXXX")"
APP="$BUILD/U1 OS.app"
SDKROOT="$(/usr/bin/xcrun --show-sdk-path)"
SWIFTC="$(/usr/bin/xcrun --find swiftc)"
export SDKROOT MACOSX_DEPLOYMENT_TARGET=12.0
mkdir -p "$BUILD/module-cache" "$BUILD/U1.iconset" "$APP/Contents/MacOS" "$APP/Contents/Resources"
"$SWIFTC" -O -sdk "$SDKROOT" -module-cache-path "$BUILD/module-cache" "$ROOT/macos/NavigationPolicy.swift" "$ROOT/macos/PolicyChecks.swift" -o "$BUILD/policy-checks"
"$BUILD/policy-checks"
"$SWIFTC" -O -sdk "$SDKROOT" -module-cache-path "$BUILD/module-cache" -framework AppKit -framework WebKit -framework ServiceManagement "$ROOT/macos/NavigationPolicy.swift" "$ROOT/macos/U1OS.swift" -o "$APP/Contents/MacOS/U1OS"
"$SWIFTC" -O -sdk "$SDKROOT" -module-cache-path "$BUILD/module-cache" -framework AppKit "$ROOT/macos/RenderIcon.swift" -o "$BUILD/render-icon"
"$BUILD/render-icon" "$BUILD/icon-1024.png"
for pixels in 16 32 128 256 512; do
  /usr/bin/sips -z "$pixels" "$pixels" "$BUILD/icon-1024.png" --out "$BUILD/U1.iconset/icon_${pixels}x${pixels}.png" >/dev/null
  double=$((pixels * 2))
  /usr/bin/sips -z "$double" "$double" "$BUILD/icon-1024.png" --out "$BUILD/U1.iconset/icon_${pixels}x${pixels}@2x.png" >/dev/null
done
/usr/bin/iconutil -c icns "$BUILD/U1.iconset" -o "$APP/Contents/Resources/U1.icns"
/usr/bin/python3 -B "$ROOT/macos/release_support.py" metadata "$APP" "$ROOT"
/usr/bin/plutil -lint "$APP/Contents/Info.plist"
/usr/bin/codesign --force --sign - "$APP"
/usr/bin/codesign --verify --strict "$APP"
/usr/bin/python3 -B "$ROOT/macos/release_support.py" promote "$APP" "$ROOT/dist/U1 OS.app"
printf 'PASS: compiled app, icon, metadata, native policy checks and ad-hoc signature integrity.\n'
printf 'Built local desktop application: %s/dist/U1 OS.app\n' "$ROOT"
printf 'No Developer ID certificate was used. Not notarised, not self-contained; Desktop was not changed.\n'
