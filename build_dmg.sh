#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DMG_NAME="CommandCenter-v2.5.0.dmg"
DMG_PATH="$DIR/$DMG_NAME"
STAGING_DIR="$DIR/dist/dmg_staging"

echo "📦 Creating macOS Drag-and-Drop .dmg Installer..."

# Ensure CommandCenter.app exists and is signed
if [ ! -d "$DIR/CommandCenter.app" ]; then
    echo "Building CommandCenter.app first..."
    bash "$DIR/build_macos_app.sh"
fi

codesign --force --deep --sign - "$DIR/CommandCenter.app"

# Clean staging directory
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

# Copy App to staging
cp -R "$DIR/CommandCenter.app" "$STAGING_DIR/"

# Create /Applications symlink for drag-and-drop installation
ln -s /Applications "$STAGING_DIR/Applications"

# Remove any old DMG
rm -f "$DMG_PATH"

# Build DMG using hdiutil
hdiutil create -volname "Command Center OS" \
  -srcfolder "$STAGING_DIR" \
  -ov -format UDZO \
  "$DMG_PATH"

# Clean staging
rm -rf "$STAGING_DIR"

echo "✅ DMG Installer built successfully: $DMG_PATH"
