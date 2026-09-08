#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/.runtime/swift-module-cache"
SDKROOT="$(/usr/bin/xcrun --sdk macosx --show-sdk-path)"
/usr/bin/xcrun swiftc -sdk "$SDKROOT" -module-cache-path "$ROOT/.runtime/swift-module-cache" "$ROOT/macos/U1Keychain.swift" -o "$ROOT/.runtime/u1-keychain"
/usr/bin/codesign --force --sign - "$ROOT/.runtime/u1-keychain"
printf 'Built the local Keychain helper. No credentials were read or changed.\n'
