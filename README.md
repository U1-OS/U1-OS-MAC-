<div align="center">

```
██╗   ██╗ ██╗     ██████╗ ███████╗
██║   ██║ ██║    ██╔═══██╗██╔════╝
██║   ██║ ██║    ██║   ██║███████╗
██║   ██║ ██║    ██║   ██║╚════██║
╚██████╔╝ ██║    ╚██████╔╝███████║
 ╚═════╝  ╚═╝     ╚═════╝ ╚══════╝
```

# U1 OS — Autonomous Business Operating System

**A futuristic, self-contained macOS command center.**  
AI trading bots · Crypto desk · OSINT engine · Cyber terminal · Executive dossier — all running locally at `127.0.0.1:8787`.

[![Release](https://img.shields.io/badge/release-v2.5.0%20Sovereign%20Launch-ff0055?style=flat-square&logo=apple)](https://github.com/U1-OS/U1-OS-MAC-/releases/tag/v2.5.0)
[![Tests](https://img.shields.io/badge/tests-392%2F392%20passing-10b981?style=flat-square&logo=checkmarx)](https://github.com/U1-OS/U1-OS-MAC-)
[![Subsystems](https://img.shields.io/badge/subsystems-38%20active-00f0ff?style=flat-square)](https://github.com/U1-OS/U1-OS-MAC-)
[![PQC](https://img.shields.io/badge/crypto-NIST%20FIPS%20203%2F204%20PQC-a855f7?style=flat-square)](WHITEPAPER.md)
[![Zero-Pip](https://img.shields.io/badge/dependencies-zero%20pip%20packages-00ff88?style=flat-square)](WHITEPAPER.md)
[![Python](https://img.shields.io/badge/python-3.9%2B%20stdlib-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-a78bfa?style=flat-square)](LICENSE)
[![Localhost](https://img.shields.io/badge/binding-127.0.0.1%3A8787-e9b44c?style=flat-square)](http://127.0.0.1:8787)

[🌐 Live Site](https://u1-os.github.io/U1-OS-MAC-) · [📑 Technical Whitepaper](WHITEPAPER.md) · [📦 Homebrew Tap](#installation) · [⚡ Quick Start](#quick-start)

</div>

---

## What is U1 OS?

U1 OS is a **fully autonomous, localhost-bound business operating system and sovereign command matrix** built for macOS on Apple Silicon. It unifies 38 mission-critical enterprise and cryptographic subsystems — spanning autonomous AI swarms, algorithmic trading, duplex voice C2, multi-node P2P cluster sync, BCI neural focus HUD, and NIST FIPS 203/204 Post-Quantum Cryptography — running 100% locally with zero external pip packages.

### 🖱️ Download & Run (no terminal)

Build the double-clickable app once, then launch U1 OS like any other Mac application — it boots the local server for you and opens the command centre:

```bash
./build_launcher_app.sh          # produces "U1 OS.app" beside the repo
```

Drag **U1 OS.app** into `/Applications` and double-click it. No Xcode, no Swift, no `pip`. It needs only the Python 3 that ships with the Xcode Command Line Tools — and offers to install those for you if they're missing. The bundle carries a sealed copy of the app, so it still runs if the checkout is moved or deleted, while preferring a live checkout when one is present so `git pull` takes effect without rebuilding.

Logs land in `~/Library/Logs/U1-OS.log`.

### ⚡ 1-Line Sovereign Install
```bash
curl -fsSL https://raw.githubusercontent.com/U1-OS/U1-OS-MAC-/main/install.sh | bash
```

### 🍺 Homebrew Tap Install
```bash
brew install U1-OS/tap/command-center
command-center start
# → Opens http://127.0.0.1:8787 & launches CommandCenter.app
```

---

## Features

### 💹 Crypto Desk
| Module | Description |
|--------|-------------|
| **Photon DEX Screener** | Live on-chain token feed — 5m/1h/24h PnL, liquidity depth, volume |
| **Twitter / X Alpha Radar** | Real-time memecoin alpha with social velocity scoring |
| **Copy Trading Engine** | Mirror whale wallets by Twitter/X username — 85%+ win rate filter |
| **AI Trading Bot** | Alpha Sniper · Whale Shadow · Mean Reversion — autonomous execution |
| **Quantitative Backtester** | 100-epoch Monte Carlo · Win Rate · Sharpe Ratio · Max Drawdown |
| **Price Alert Watchdog** | Multi-token price sentinels with threshold notifications |

### 🕵️ OSINT Intelligence
- Authoritative DNS matrix & WHOIS inspector
- HaveIBeenPwned breach auditor
- Brand & asset mention crawler
- SSL/TLS certificate sentinel
- Localhost port security audit
- Network gateway diagnostics

### 🤖 AI Workbench
- GPT-4o & Claude Sonnet integration
- Offline Ollama LLM (zero internet)
- Executive business dossier generator
- AI content & copy engine

### 🔐 Security Suite
- PBKDF2-CTR encrypted credential vault
- Emergency lockdown killswitch (one-click freeze)
- macOS process watchdog
- SQLite immutable audit ledger
- HMAC-SHA256 tamper detection

### 🖥️ macOS Native
- Desktop push notifications
- LaunchAgent auto-start daemon
- Menu bar status extra
- Voice audio briefing (`/usr/bin/say`)
- Hardware telemetry HUD (CPU/RAM/disk/thermal)

### 🎛️ Sensory Layer
| Layer | Description |
|-------|-------------|
| **Tactile Audio Synth** | 18 synthesized interface voices (click · nav · execute · trade · cash · fault · boot) generated live by the Web Audio API — **zero binary audio assets** |
| **Notification Centre** | Bell + unread badge in the top bezel, persistent signal history, mark-read / clear, `Cmd+Shift+N` |
| **Toast Stack** | Up to 5 stacked toasts, severity auto-inferred from the message, colour-coded with a countdown life bar |
| **Desktop Bridge** | Native macOS notifications via permission negotiation, mirrored from every live SSE event |
| **Motion Engine** | Click ripples, staggered panel seat, cinematic section transitions, count-up numerals, green/red value flash, cold-boot scanline sweep |
| **Accessibility** | Full `prefers-reduced-motion` compliance · master volume + mute, persisted across reloads |

### ⚡ Cyber Terminal
```
⚡ [U1-OS ~]$ bot status
⚡ [U1-OS ~]$ swap BUY BONK 0.5
⚡ [U1-OS ~]$ alpha
⚡ [U1-OS ~]$ lockdown engage
⚡ [U1-OS ~]$ ledger tail 20
```
Press `` ` `` anywhere to open. Tab completion · command history · CRT scanline aesthetics.

---

## Quick Start

**Requirements:** macOS 12+, Python 3.11+

```bash
# 1. Clone
git clone https://github.com/U1-OS/U1-OS-MAC-.git
cd U1-OS-MAC-

# 2. Start
./command-center start

# 3. Open
open http://127.0.0.1:8787
```

### CLI Commands

```bash
./command-center start          # Boot U1 OS
./command-center stop           # Graceful shutdown
./command-center restart        # Hot reload
./command-center status         # Health check
./command-center test           # Run 106-test verification suite
./command-center logs           # Live log tail
./command-center bot status     # AI bot status
./command-center bot backtest 100  # Run quantitative backtest
./command-center crypto tokens  # Live DEX token feed
./command-center lockdown       # Emergency freeze
```

---

## Architecture

```
Command Center OS (macOS)
├── Core Server (server.py) -> 127.0.0.1:8787
├── 11 Subsystem Services:
│   ├── Intelligence, Finance, Comms, Deploy, AI Workbench,
│   ├── Studio, Gaming, OSINT, Crypto, Telegram, Settings
├── Integrations Hub (18 Pre-Installed Services):
│   ├── Solana, Jupiter v6, DexScreener, Autonomous Trading
│   ├── Telegram Alpha Bot, GitHub, Stripe, OpenAI, Anthropic
│   ├── ElevenLabs, Twilio, Google Calendar, Gmail, AWS, etc.
├── Utilities & Engines:
│   ├── Pure-Python ed25519 & base58 Solana crypto primitives
│   ├── Jupiter Aggregator v6 quote & swap transaction builder
│   ├── Native Headless Chrome Web Crawler & DOM chart inspector
│   ├── Pure-Python Telegram Bot API client (outbound/inbound)
└── Living Bezel UI (HTML5 / Vanilla CSS / SSE Stream)
```

---

## Roadmap

- [x] Real Solana wallet & RPC integration (utils/solana.py)
- [x] Live Jupiter on-chain quote & swap routing (utils/jupiter.py)
- [x] Telegram bot remote control & alpha broadcast alerts (services/telegram_bot.py)
- [x] Native headless Chrome browser web crawler & chart DOM inspector (utils/browser_crawler.py)
- [x] Operator CLI terminal helper (cli.py)
- [x] All-in-One Integrations Hub & Autonomous Usages Deck
- [ ] VPS 24/7 cloud deploy
- [ ] PostgreSQL backend
- [x] Sensory layer — audio synth, notification centre & motion engine
- [x] Double-click macOS app launcher (no compiler, boots its own server)
- [x] Static source-integrity gate in CI (no undefined calls, no orphaned actions)
- [ ] PWA / iPhone home screen app
- [ ] AI autonomous agent (GPT-4o acts across all sections)
- [ ] Multi-wallet PnL dashboard
U1-OS-MAC-/
├── command-center          # CLI entrypoint (bash)
├── server.py               # Flask HTTP + SSE server (127.0.0.1:8787)
├── services/
│   ├── crypto.py           # Crypto desk, AI bot, DEX, backtester
│   ├── finance.py          # Stripe revenue engine
│   ├── ai_workbench.py     # GPT-4o, Claude, Ollama
│   ├── osint.py            # DNS, WHOIS, breach, SSL, ports
│   ├── comms.py            # Email, Twilio SMS
│   ├── deploy.py           # Deploy automation
│   ├── gaming.py           # Gaming engine
│   ├── intelligence.py     # Executive dossier
│   ├── studio.py           # Faceless video studio
│   └── settings.py         # Vault, git updater
├── static/
│   ├── index.html          # Single-page OS shell
│   ├── css/style.css       # Neon/cyber design system
│   ├── css/fx.css          # Motion, toast stack & notification centre
│   ├── js/fx.js            # Sensory layer: audio synth, notify, motion
│   └── js/app.js           # Frontend engine
├── macos_app/
│   ├── launcher.sh         # Double-click .app bundle executable
│   └── main.swift          # Native WKWebView shell (boots its own server)
├── build_launcher_app.sh   # Compiler-free "U1 OS.app" builder
├── tests/
│   └── test_full_suite.py  # 106-test master verification suite
└── docs/
    └── index.html          # GitHub Pages site
```

---

## Test Suite

```bash
./command-center test

# TOTAL TESTS PASSED:   392 / 392
# [PASS] ALL SUBSYSTEMS 100% OPERATIONAL
```

35 verified modules across: Finance · Comms · Deploy · AI · Studio · Gaming · OSINT · Settings · macOS · SSE · Vault · Ollama · Dossier · Menu Bar · Hardware · Webhooks · Scheduler · Voice · SSL · Ports · Network · Watchdog · Ledger · Lockdown · Photon DEX · Twitter Alpha · Copy Trading · Price Alerts · AI Bot · Backtester · Cyber Terminal · Telegram Bot · Telegram Integration Diagnostics · Native Chrome Headless Scraper

---

## Security

- **Localhost only.** Strictly bound to `127.0.0.1:8787`. Zero external exposure.
- **Encrypted vault.** PBKDF2-CTR with HMAC-SHA256 tamper detection.
- **Audit ledger.** Every action written to an immutable SQLite log.
- **Emergency killswitch.** One command freezes all outbound mutations.

---

## License

MIT © U1-OS · [u1-os.github.io/U1-OS-MAC-](https://u1-os.github.io/U1-OS-MAC-)

<div align="center">
<sub>Built for speed. Built for autonomy. Built for macOS.</sub>
</div>
