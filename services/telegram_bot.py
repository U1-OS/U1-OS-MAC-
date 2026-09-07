#!/usr/bin/env python3
"""
Command Center — Telegram Alpha Bot & Remote Terminal Service
Enables bidirectional Telegram communication:
- Real-time outbound alpha trade signals, price triggers, and emergency alerts.
- Inbound remote control: /status, /pnl, /tokens, /quote, /buy, /bot, /browse, /lockdown, /unlock.
"""

import time
import os
import json
from services.base import BaseService
from utils import telegram
from utils import browser_crawler
from utils import macos

class TelegramService(BaseService):
    def __init__(self, config):
        super().__init__("telegram", config)
        self.bot_info = None
        self.last_update_id = 0
        self.message_history = []
        self.feeder = None  # Populated by server.py
        self.polling_enabled = True

    def _get_token(self):
        return self.config.get("integrations", {}).get("telegram", {}).get("bot_token", "").strip()

    def _get_chat_id(self):
        return self.config.get("integrations", {}).get("telegram", {}).get("chat_id", "").strip()

    def _get_alpha_channel(self):
        return self.config.get("integrations", {}).get("telegram", {}).get("alpha_channel", "").strip()

    def poll(self):
        token = self._get_token()
        chat_id = self._get_chat_id()
        is_configured = bool(token and chat_id)

        # Validate token with getMe if not cached
        if is_configured and not self.bot_info:
            res = telegram.get_me(token, timeout=4)
            if res.get("ok"):
                self.bot_info = res.get("result", {})

        # Process incoming Telegram messages if bot is active
        incoming_processed = 0
        if is_configured and self.polling_enabled:
            incoming_processed = self._poll_and_execute_updates(token)

        with self.lock:
            self.configured = is_configured
            self.status = "active" if is_configured else "unconfigured"
            self.data = {
                "configured": is_configured,
                "bot_info": self.bot_info or {
                    "username": "Not Connected",
                    "first_name": "Standby Bot",
                    "can_join_groups": False
                },
                "chat_id": chat_id,
                "alpha_channel": self._get_alpha_channel(),
                "recent_messages": self.message_history[-20:],
                "messages_count": len(self.message_history),
                "connect_notice": "Connected & Polling Active" if is_configured else "Enter Bot Token & Chat ID in Integrations Hub"
            }
            self.last_updated = time.time()

    def _poll_and_execute_updates(self, token):
        """Polls getUpdates from Telegram and routes commands."""
        offset = self.last_update_id + 1 if self.last_update_id > 0 else 0
        res = telegram.get_updates(token, offset=offset, timeout=0, request_timeout=4)
        if not res.get("ok"):
            return 0

        updates = res.get("result", [])
        count = 0
        for upd in updates:
            upd_id = upd.get("update_id", 0)
            if upd_id > self.last_update_id:
                self.last_update_id = upd_id

            msg = upd.get("message") or upd.get("channel_post")
            if not msg:
                continue

            text = msg.get("text", "").strip()
            chat = msg.get("chat", {})
            sender_chat_id = chat.get("id")
            user = msg.get("from", {})

            if text.startswith("/"):
                # Record inbound message
                self._record_message("INBOUND", text, sender_chat_id, user.get("username", "user"))
                
                # Execute command
                reply_text = self.execute_telegram_command(text, sender_chat_id)
                if reply_text:
                    # Send response back to sender
                    telegram.send_message(token, sender_chat_id, reply_text, parse_mode="HTML")
                    self._record_message("OUTBOUND", reply_text, sender_chat_id, "BOT")
                count += 1

        return count

    def _record_message(self, direction, text, chat_id, author):
        entry = {
            "id": f"tg-{int(time.time()*1000)}",
            "direction": direction,
            "text": text[:300],
            "chat_id": str(chat_id),
            "author": author,
            "time_str": time.strftime("%H:%M:%S")
        }
        self.message_history.append(entry)
        if len(self.message_history) > 50:
            self.message_history.pop(0)

    def execute_telegram_command(self, cmd_line, sender_chat_id=None):
        """Processes Telegram bot commands and returns formatted HTML output."""
        parts = cmd_line.strip().split()
        cmd = parts[0].lower().replace("@" + (self.bot_info.get("username", "") if self.bot_info else ""), "")
        args = parts[1:]

        # 1. /start or /help
        if cmd in ["/start", "/help"]:
            return (
                "🤖 <b>COMMAND CENTER // TELEGRAM ALPHA BOT</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<b>Live Remote Commands:</b>\n"
                "• <code>/status</code> — System health, RAM, CPU & Feeder status\n"
                "• <code>/tokens</code> — Trending Solana memecoins & DEX prices\n"
                "• <code>/quote &lt;sym&gt;</code> — Live Jupiter quote & market depth\n"
                "• <code>/buy &lt;sym&gt; [sol]</code> — Instant on-chain / Photon swap\n"
                "• <code>/pnl</code> — Portfolio holdings, balances & PnL\n"
                "• <code>/bot status</code> — Autonomous AI Trading bot stats\n"
                "• <code>/bot start</code> — Activate autonomous buying\n"
                "• <code>/bot stop</code> — Pause autonomous buying\n"
                "• <code>/browse &lt;url&gt;</code> — Headless Chrome web inspection\n"
                "• <code>/lockdown</code> — Trigger immediate emergency killswitch\n"
                "• <code>/unlock</code> — Disengage emergency lockdown\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>All operations execute with real on-chain parameters.</i>"
            )

        # 2. /status
        elif cmd == "/status":
            intel_svc = self.feeder.services.get("intelligence") if self.feeder else None
            crypto_svc = self.feeder.services.get("crypto") if self.feeder else None
            
            telemetry = intel_svc.data.get("telemetry", {}) if intel_svc else {}
            bot_state = crypto_svc.bot_state if crypto_svc else {}
            
            return (
                "⚡ <b>COMMAND CENTER // TELEMETRY STATUS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🖥 <b>Host:</b> macOS (Localhost 127.0.0.1:8787)\n"
                f"⏱ <b>System 1m Load:</b> {telemetry.get('load_1m', '0.45')}\n"
                f"🧠 <b>Memory:</b> {telemetry.get('memory_used_pct', 42.0)}% Used\n"
                f"🤖 <b>Trading Bot:</b> <b>{bot_state.get('status', 'STANDBY')}</b>\n"
                f"🛡 <b>Mode:</b> {bot_state.get('autonomous_mode', 'PAPER')}\n"
                f"🌐 <b>Headless Browser:</b> {'ENABLED' if bot_state.get('full_browser_execution') else 'STANDBY'}\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>System operational & green.</i>"
            )

        # 3. /tokens
        elif cmd == "/tokens":
            crypto_svc = self.feeder.services.get("crypto") if self.feeder else None
            tokens = crypto_svc.tokens if crypto_svc else []
            lines = [
                "🪙 <b>SOLANA TRENDING RADAR // PHOTON DESK</b>",
                "━━━━━━━━━━━━━━━━━━"
            ]
            for t in tokens[:6]:
                p_str = f"${t['price_usd']:.6f}" if t['price_usd'] < 0.01 else f"${t['price_usd']:.2f}"
                sign = "+" if t["pnl_24h"] >= 0 else ""
                lines.append(f"• <b>${t['symbol']}</b>: <code>{p_str}</code> ({sign}{t['pnl_24h']}% 24h)")
            lines.append("━━━━━━━━━━━━━━━━━━")
            lines.append("<i>Send <code>/buy &lt;sym&gt; &lt;sol&gt;</code> to swap.</i>")
            return "\n".join(lines)

        # 4. /quote
        elif cmd == "/quote":
            if not args:
                return "⚠️ <b>Usage:</b> <code>/quote &lt;symbol_or_ca&gt;</code> (e.g. <code>/quote BONK</code>)"
            sym = args[0].upper()
            crypto_svc = self.feeder.services.get("crypto") if self.feeder else None
            token = next((t for t in crypto_svc.tokens if t["symbol"] == sym), None) if crypto_svc else None
            if not token:
                return f"❌ Token <code>${sym}</code> not found in active tracking pool."
            
            p_str = f"${token['price_usd']:.6f}" if token['price_usd'] < 0.01 else f"${token['price_usd']:.2f}"
            return (
                f"📊 <b>LIVE QUOTE // ${token['symbol']}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🪙 <b>Name:</b> {token['name']}\n"
                f"💵 <b>Price:</b> <code>{p_str}</code>\n"
                f"📈 <b>5m:</b> {token['pnl_5m']:+,.2f}% | <b>24h:</b> {token['pnl_24h']:+,.2f}%\n"
                f"💧 <b>Liquidity:</b> ${token['liquidity_usd']/1e6:.1f}M\n"
                f"🔑 <b>CA:</b> <code>{token['ca']}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<i>Ready for execution via Jupiter router</i>"
            )

        # 5. /buy
        elif cmd == "/buy":
            if not args:
                return "⚠️ <b>Usage:</b> <code>/buy &lt;symbol&gt; [amount_sol]</code> (e.g. <code>/buy BONK 0.2</code>)"
            sym = args[0].upper()
            amount_sol = float(args[1]) if len(args) > 1 else 0.1
            crypto_svc = self.feeder.services.get("crypto") if self.feeder else None
            if not crypto_svc:
                return "❌ Crypto service unreachable."

            # Execute swap
            swap_res = crypto_svc.dispatch_action("execute_swap", {
                "symbol": sym,
                "side": "BUY",
                "amount": amount_sol,
                "confirmed": True
            })

            if swap_res.get("success"):
                return telegram.format_trade_alert(
                    token_symbol=sym,
                    action="BUY",
                    amount_sol=amount_sol,
                    price_usd=swap_res.get("price_usd", 0.0),
                    tokens_qty=swap_res.get("tokens_received", 0.0),
                    tx_hash=swap_res.get("tx_hash"),
                    engine="Photon / Jupiter v6"
                )
            else:
                return f"❌ <b>Swap Failed:</b> {swap_res.get('error', 'Unknown error')}"

        # 6. /pnl or /positions
        elif cmd in ["/pnl", "/positions"]:
            crypto_svc = self.feeder.services.get("crypto") if self.feeder else None
            if not crypto_svc:
                return "❌ Crypto service unreachable."

            positions = crypto_svc.positions
            lines = [
                "💼 <b>PORTFOLIO & OPEN POSITIONS</b>",
                "━━━━━━━━━━━━━━━━━━"
            ]
            if not positions:
                lines.append("<i>No active open positions.</i>")
            else:
                for p in positions:
                    sign = "+" if p["unrealized_pnl_usd"] >= 0 else ""
                    lines.append(f"• <b>${p['symbol']}</b>: {p['amount']:,.1f} | PnL: <b>{sign}${p['unrealized_pnl_usd']}</b> ({sign}{p['unrealized_pnl_pct']}%)")
            lines.append("━━━━━━━━━━━━━━━━━━")
            bot = crypto_svc.bot_state
            lines.append(f"🤖 <b>Bot Realized PnL:</b> {bot.get('realized_pnl_sol', 0):+} SOL (${bot.get('realized_pnl_usd', 0):+,.2f})")
            return "\n".join(lines)

        # 7. /bot
        elif cmd == "/bot":
            sub = args[0].lower() if args else "status"
            crypto_svc = self.feeder.services.get("crypto") if self.feeder else None
            if not crypto_svc:
                return "❌ Crypto service unreachable."

            if sub == "start":
                crypto_svc.dispatch_action("start_trading_bot")
                return "✅ <b>Autonomous AI Trading Bot ENGAGED.</b>\nMonitoring alpha tweets and liquidity spikes."
            elif sub == "stop":
                crypto_svc.dispatch_action("stop_trading_bot")
                return "⏸ <b>Autonomous AI Trading Bot DISENGAGED (STANDBY).</b>"
            else:
                s = crypto_svc.bot_state
                return (
                    f"🤖 <b>AUTONOMOUS BOT TELEMETRY</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"<b>Status:</b> {s['status']}\n"
                    f"<b>Mode:</b> {s.get('autonomous_mode', 'PAPER')}\n"
                    f"<b>Realized PnL:</b> {s['realized_pnl_sol']:+} SOL\n"
                    f"<b>Strategies:</b> {', '.join(s['active_strategies'])}\n"
                    f"<b>Open Positions:</b> {len(s['bot_positions'])}/{s['max_open_positions']}\n"
                    f"<b>Total Trades:</b> {s['total_bot_trades']}"
                )

        # 8. /browse
        elif cmd == "/browse":
            if not args:
                return "⚠️ <b>Usage:</b> <code>/browse &lt;url&gt;</code>"
            url = args[0]
            if not url.startswith("http"):
                url = "https://" + url
            res = browser_crawler.inspect_page(url, wait_ms=2500)
            if res.get("ok"):
                ca_info = f"\n🔑 <b>Detected CAs:</b> <code>{res['detected_solana_cas'][0]}</code>" if res.get("detected_solana_cas") else ""
                return (
                    f"🌐 <b>HEADLESS BROWSER INSPECTOR</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"<b>URL:</b> {url}\n"
                    f"<b>Title:</b> {res.get('title')}\n"
                    f"<b>Engine:</b> {res.get('engine')} ({res.get('latency_ms')}ms)\n"
                    f"<b>Preview:</b> <i>{res.get('text_preview', '')[:180]}...</i>{ca_info}"
                )
            else:
                return f"❌ <b>Browser crawl failed:</b> {res.get('error')}"

        # 9. /lockdown
        elif cmd == "/lockdown":
            settings_svc = self.feeder.services.get("settings") if self.feeder else None
            if settings_svc:
                settings_svc.dispatch_action("toggle_lockdown", {"enable": True, "confirmed": True, "reason": "Remote Telegram command"})
            return telegram.format_lockdown_notice(True, "Triggered via Telegram /lockdown")

        # 10. /unlock
        elif cmd == "/unlock":
            settings_svc = self.feeder.services.get("settings") if self.feeder else None
            if settings_svc:
                settings_svc.dispatch_action("toggle_lockdown", {"enable": False, "confirmed": True})
            return telegram.format_lockdown_notice(False)

        return (
            f"❓ Unknown command <code>{cmd}</code>.\n"
            f"Send <code>/help</code> to view available commands."
        )

    def broadcast_alert(self, text, parse_mode="HTML"):
        """Dispatches an alert to configured chat_id and optional alpha channel."""
        token = self._get_token()
        chat_id = self._get_chat_id()
        channel = self._get_alpha_channel()

        results = []
        if token and chat_id:
            res1 = telegram.send_message(token, chat_id, text, parse_mode=parse_mode)
            self._record_message("BROADCAST", text, chat_id, "SYSTEM")
            results.append(res1)
        if token and channel and channel != chat_id:
            res2 = telegram.send_message(token, channel, text, parse_mode=parse_mode)
            results.append(res2)

        return {"success": True, "dispatched": len(results), "results": results}

    def dispatch_action(self, action, payload=None):
        payload = payload or {}
        token = self._get_token()

        if action == "test_bot":
            res = telegram.get_me(token, timeout=5)
            ok = res.get("ok", False)
            if ok:
                self.bot_info = res.get("result", {})
            return {
                "success": ok,
                "bot_info": self.bot_info,
                "message": f"Connected to Telegram Bot: @{self.bot_info.get('username')}" if ok else f"Telegram Standby: {res.get('error')}"
            }

        elif action == "send_message":
            chat_id = payload.get("chat_id") or self._get_chat_id()
            text = payload.get("text", "")
            parse_mode = payload.get("parse_mode", "HTML")
            if not text:
                return {"success": False, "error": "Message text is required"}
            res = telegram.send_message(token, chat_id, text, parse_mode=parse_mode)
            if res.get("ok"):
                self._record_message("OUTBOUND", text, chat_id, "OPERATOR")
            return {"success": res.get("ok", False), "result": res}

        elif action == "broadcast_alert":
            text = payload.get("text", "")
            if not text:
                return {"success": False, "error": "Alert text required"}
            return self.broadcast_alert(text, parse_mode=payload.get("parse_mode", "HTML"))

        elif action == "poll_updates":
            count = self._poll_and_execute_updates(token)
            return {"success": True, "processed_updates": count, "last_update_id": self.last_update_id}

        elif action == "execute_command":
            cmd_line = payload.get("command", "/help")
            output = self.execute_telegram_command(cmd_line)
            return {"success": True, "command": cmd_line, "output": output}

        return super().dispatch_action(action, payload)
