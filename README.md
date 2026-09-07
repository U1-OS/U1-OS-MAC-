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

[![Tests](https://img.shields.io/badge/tests-95%2F95%20passing-10b981?style=flat-square&logo=checkmarx)](https://github.com/U1-OS/U1-OS-MAC-)
[![Subsystems](https://img.shields.io/badge/subsystems-32%20active-00f0ff?style=flat-square)](https://github.com/U1-OS/U1-OS-MAC-)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-a78bfa?style=flat-square)](LICENSE)
[![GitHub Pages](https://img.shields.io/badge/site-live-10b981?style=flat-square&logo=github)](https://u1-os.github.io/U1-OS-MAC-)
[![Localhost](https://img.shields.io/badge/binding-127.0.0.1%3A8787-e9b44c?style=flat-square)](http://127.0.0.1:8787)

[🌐 Live Site](https://u1-os.github.io/U1-OS-MAC-) · [📖 Docs](#quick-start) · [🚀 Features](#features) · [⚡ Install](#quick-start)

</div>

---

## What is U1 OS?

U1 OS is a **fully autonomous, localhost-bound business operating system** built for macOS. It replaces dozens of SaaS dashboards with a single, neon-lit command center that runs entirely on your machine — no cloud, no subscriptions, no data leaving your device.

```bash
git clone https://github.com/U1-OS/U1-OS-MAC-.git
cd U1-OS-MAC-
./command-center start
# → http://127.0.0.1:8787
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
./command-center test           # Run 103-test verification suite
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
│   └── js/app.js           # Frontend engine
├── tests/
│   └── test_full_suite.py  # 103-test master verification suite
└── docs/
    └── index.html          # GitHub Pages site
```

---

## Test Suite

```bash
./command-center test

# TOTAL TESTS PASSED:   103 / 103
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
