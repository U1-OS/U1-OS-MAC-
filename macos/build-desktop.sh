#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/.runtime/u1-desktop"
APP="$ROOT/dist/U1 OS.app"
mkdir -p "$BUILD/module-cache" "$BUILD/U1.iconset" "$APP/Contents/MacOS" "$APP/Contents/Resources"
SWIFTC="$(/usr/bin/xcrun --find swiftc)"
"$SWIFTC" -O -module-cache-path "$BUILD/module-cache" -framework AppKit -framework WebKit "$ROOT/macos/U1OS.swift" -o "$APP/Contents/MacOS/U1OS"
"$SWIFTC" -O -module-cache-path "$BUILD/module-cache" -framework AppKit "$ROOT/macos/RenderIcon.swift" -o "$BUILD/render-icon"
"$BUILD/render-icon" "$BUILD/icon-1024.png"
for pixels in 16 32 128 256 512; do
  /usr/bin/sips -z "$pixels" "$pixels" "$BUILD/icon-1024.png" --out "$BUILD/U1.iconset/icon_${pixels}x${pixels}.png" >/dev/null
  double=$((pixels * 2))
  /usr/bin/sips -z "$double" "$double" "$BUILD/icon-1024.png" --out "$BUILD/U1.iconset/icon_${pixels}x${pixels}@2x.png" >/dev/null
done
/usr/bin/iconutil -c icns "$BUILD/U1.iconset" -o "$APP/Contents/Resources/U1.icns"
U1_BUILD_ROOT="$ROOT" U1_BUILD_APP="$APP" /usr/bin/python3 - <<'PY'
import os
import plistlib
from pathlib import Path
info = dict(CFBundleExecutable='U1OS', CFBundleIdentifier='local.u1os.business',
            CFBundleName='U1 OS', CFBundleDisplayName='U1 OS', CFBundlePackageType='APPL',
            CFBundleShortVersionString='1.0.0', CFBundleVersion='1', CFBundleIconFile='U1.icns',
            LSMinimumSystemVersion='12.0', NSHighResolutionCapable=True,
            NSAppTransportSecurity={'NSAllowsLocalNetworking': True},
            U1WorkspaceRoot=os.environ['U1_BUILD_ROOT'])
with (Path(os.environ['U1_BUILD_APP']) / 'Contents/Info.plist').open('wb') as handle:
    plistlib.dump(info, handle)
PY
/usr/bin/codesign --force --sign - "$APP"
printf 'Built local desktop application: %s\n' "$APP"
printf 'This app uses the existing workspace and runtime; it is not a self-contained notarized distribution.\n'
