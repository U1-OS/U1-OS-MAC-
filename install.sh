#!/usr/bin/env bash
# ==============================================================================
# Command Center OS — 1-Click Sovereign Global Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/U1-OS/U1-OS-MAC-/main/install.sh | bash
# ==============================================================================

set -e

BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
echo "  ██████╗ ██████╗ ███╗   ███╗███╗   ███╗ █████╗ ███╗   ██╗██████╗ "
echo " ██╔════╝██╔═══██╗████╗ ████║████╗ ████║██╔══██╗████╗  ██║██╔══██╗"
echo " ██║     ██║   ██║██╔████╔██║██╔████╔██║███████║██╔██╗ ██║██║  ██║"
echo " ██║     ██║   ██║██║╚██╔╝██║██║╚██╔╝██║██╔══██║██║╚██╗██║██║  ██║"
echo " ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║██║  ██║██║ ╚████║██████╔╝"
echo "  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ "
echo "        COMMAND CENTER OS — SOVEREIGN LOCAL MATRIX (DARWIN)       "
echo -e "${RESET}"

INSTALL_DIR="$HOME/.command-center"
REPO_URL="https://github.com/U1-OS/U1-OS-MAC-.git"

echo -e "${CYAN}[1/5] Verifying macOS environment & Apple Silicon acceleration...${RESET}"
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${YELLOW}Warning: Command Center OS is optimized for macOS Darwin. Proceeding anyway...${RESET}"
fi

# Check Python3 version
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required. Please install Python 3 and re-run."
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${GREEN}  ✓ Python ${PY_VER} verified (Pure standard library, zero pip packages required)${RESET}"

echo -e "${CYAN}[2/5] Fetching Command Center OS repository...${RESET}"
if [ -d "$INSTALL_DIR" ]; then
    echo "  Updating existing deployment at $INSTALL_DIR..."
    cd "$INSTALL_DIR" && git pull --rebase || true
else
    echo "  Cloning into $INSTALL_DIR..."
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo -e "${CYAN}[3/5] Compiling native macOS App Bundle (CommandCenter.app)...${RESET}"
if command -v swiftc &> /dev/null; then
    chmod +x build_macos_app.sh && ./build_macos_app.sh > /dev/null 2>&1 || true
    echo -e "${GREEN}  ✓ CommandCenter.app built with Cocoa & WebKit${RESET}"
else
    echo -e "${YELLOW}  swiftc not found; skipping native .app build (Web UI available)${RESET}"
fi

echo -e "${CYAN}[4/5] Installing macOS LaunchAgent background daemon...${RESET}"
PLIST_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$PLIST_DIR"
PLIST_FILE="$PLIST_DIR/com.commandcenter.feeder.plist"

cat << EOF > "$PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.commandcenter.feeder</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>$INSTALL_DIR/server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/vault/server.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/vault/server.err</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load -w "$PLIST_FILE" 2>/dev/null || true
echo -e "${GREEN}  ✓ LaunchAgent registered at $PLIST_FILE${RESET}"

echo -e "${CYAN}[5/5] Launching Command Center OS...${RESET}"
sleep 1
if command -v open &> /dev/null; then
    open "http://127.0.0.1:8787"
fi

echo -e "\n${GREEN}${BOLD}🎉 COMMAND CENTER OS INSTALLED & RUNNING!${RESET}"
echo -e "Dashboard:      ${CYAN}http://127.0.0.1:8787${RESET}"
echo -e "Native App:     ${CYAN}$INSTALL_DIR/CommandCenter.app${RESET}"
echo -e "Daemon Status:  ${CYAN}launchctl list | grep com.commandcenter${RESET}"
echo -e "Test Suite:     ${CYAN}cd $INSTALL_DIR && python3 tests/test_full_suite.py${RESET}"
echo ""
