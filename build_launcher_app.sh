#!/usr/bin/env bash
#
# U1 OS // Zero-Dependency App Builder  (Wave 10)
# ---------------------------------------------------------------
# Builds a double-clickable "U1 OS.app" that boots the server and
# opens the command centre. Unlike build_macos_app.sh this needs
# no Swift toolchain and no Xcode — a .app is just a folder, so it
# builds anywhere and runs on any Mac with Python 3.
#
#   ./build_launcher_app.sh              -> builds beside the repo
#   ./build_launcher_app.sh ~/Desktop    -> builds into a folder
#
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-$DIR}"
APP="$DEST/U1 OS.app"
VERSION="2.5.0"

echo "⚡ Building U1 OS.app (launcher edition, v$VERSION)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources/app"

# 1. Bundle executable
cp "$DIR/macos_app/launcher.sh" "$APP/Contents/MacOS/U1 OS"
chmod +x "$APP/Contents/MacOS/U1 OS"

# 2. Seal a standalone copy of the payload so the app still works
#    if it is moved to another Mac or the checkout is deleted.
for item in server.py cli.py config.json command-center services static utils vault docs; do
  [ -e "$DIR/$item" ] && cp -R "$DIR/$item" "$APP/Contents/Resources/app/" 2>/dev/null || true
done
find "$APP/Contents/Resources/app" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find "$APP/Contents/Resources/app" -name '*.pyc' -delete 2>/dev/null || true

# 3. Remember where this was built from, so a live checkout wins
echo "$DIR" > "$APP/Contents/Resources/source_path"

# 4. Icon (reuses the app favicon if iconutil is available)
if [ -f "$DIR/static/favicon.svg" ] && command -v qlmanage >/dev/null 2>&1; then
  cp "$DIR/static/favicon.svg" "$APP/Contents/Resources/favicon.svg" 2>/dev/null || true
fi

# 5. Info.plist
cat << PLIST > "$APP/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>U1 OS</string>
    <key>CFBundleIdentifier</key>
    <string>com.u1os.launcher</string>
    <key>CFBundleName</key>
    <string>U1 OS</string>
    <key>CFBundleDisplayName</key>
    <string>U1 OS</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
        <key>NSAllowsLocalNetworking</key>
        <true/>
    </dict>
</dict>
</plist>
PLIST

# 6. Ad-hoc sign when running on a Mac, so Gatekeeper is happy
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$APP" >/dev/null 2>&1 && echo "   ✓ ad-hoc signed" || true
fi

# 7. Clear the quarantine flag if the tool exists
command -v xattr >/dev/null 2>&1 && xattr -cr "$APP" 2>/dev/null || true

SIZE=$(du -sh "$APP" 2>/dev/null | cut -f1)
echo "✅ Built: $APP  ($SIZE)"
echo "   Double-click it, or drag it into /Applications."
