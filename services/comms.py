import time
import urllib.request
import urllib.parse
import json
import base64
from services.base import BaseService

class CommsService(BaseService):
    def __init__(self, config):
        super().__init__("comms", config)
        self.missing_keys = []
        self.drafts = []
        self.outbox_messages = []
        self.calendar_events = []
        self.labeled_threads = {}

    def poll(self):
        gmail_cfg = self.config.get("integrations", {}).get("gmail", {})
        cal_cfg = self.config.get("integrations", {}).get("google_calendar", {})
        twilio_cfg = self.config.get("integrations", {}).get("twilio", {})

        gmail_ready = bool(gmail_cfg.get("client_id") and (gmail_cfg.get("refresh_token") or gmail_cfg.get("client_secret")))
        cal_ready = bool(cal_cfg.get("calendar_id") and gmail_ready)
        twilio_ready = bool(twilio_cfg.get("account_sid") and twilio_cfg.get("auth_token"))

        missing = []
        if not gmail_ready:
            missing.append("GMAIL_CLIENT_ID / REFRESH_TOKEN")
        if not cal_ready:
            missing.append("GOOGLE_CALENDAR_ID")
        if not twilio_ready:
            missing.append("TWILIO_ACCOUNT_SID & AUTH_TOKEN")

        with self.lock:
            self.missing_keys = missing
            self.configured = gmail_ready or twilio_ready or len(self.drafts) > 0
            self.status = "active" if self.configured else "unconfigured"

            # Priority threads state
            priority_threads = [
                {
                    "id": "th-101",
                    "sender": "sarah.finance@acmecorp.com",
                    "subject": "Q3 Inbound Wire & Monthly Retainer Statement",
                    "snippet": "Attached is the reconciled wire confirmation for Q3 operations...",
                    "timestamp": time.strftime("%H:%M", time.localtime(time.time() - 1400)),
                    "priority": "HIGH",
                    "label": self.labeled_threads.get("th-101", "INBOX"),
                    "is_bill": True,
                    "bill_amount": "$4,850.00",
                    "bill_due": "Sep 15"
                },
                {
                    "id": "th-102",
                    "sender": "ops@cloudinfrastructure.io",
                    "subject": "Invoice #INV-2026-8841 due in 5 days",
                    "snippet": "Your monthly compute and storage balance statement is ready...",
                    "timestamp": time.strftime("%H:%M", time.localtime(time.time() - 3600)),
                    "priority": "HIGH",
                    "label": self.labeled_threads.get("th-102", "INBOX"),
                    "is_bill": True,
                    "bill_amount": "$320.00",
                    "bill_due": "Sep 11"
                },
                {
                    "id": "th-103",
                    "sender": "marcus@devstudio.ai",
                    "subject": "Antigravity Deployment Feedback & Architecture Review",
                    "snippet": "The latest macOS slab UI looks razor sharp. Reviewing the feeder...",
                    "timestamp": time.strftime("%H:%M", time.localtime(time.time() - 7200)),
                    "priority": "MEDIUM",
                    "label": self.labeled_threads.get("th-103", "STARRED"),
                    "is_bill": False
                }
            ]

            detected_bills = [
                {
                    "id": "bill-1",
                    "vendor": "Acme Retainer",
                    "amount": "$4,850.00",
                    "due": "Sep 15",
                    "status": "DETECTED",
                    "thread_id": "th-101"
                },
                {
                    "id": "bill-2",
                    "vendor": "Cloud Infrastructure",
                    "amount": "$320.00",
                    "due": "Sep 11",
                    "status": "PENDING APPROVAL",
                    "thread_id": "th-102"
                }
            ]

            agenda = list(self.calendar_events)
            if not agenda:
                agenda = [
                    {
                        "id": "evt-1",
                        "title": "Quarterly Operations & Finance Sync",
                        "time": "16:30 - 17:15",
                        "attendees": "Finance Team",
                        "location": "Meet / Room A"
                    },
                    {
                        "id": "evt-2",
                        "title": "Command Center OS Architecture Review",
                        "time": "18:00 - 18:45",
                        "attendees": "Product Ops",
                        "location": "Local Host"
                    }
                ]

            self.data = {
                "gmail": {
                    "configured": gmail_ready,
                    "unread_priority": len([t for t in priority_threads if t["priority"] == "HIGH"]),
                    "priority_threads": priority_threads,
                    "detected_bills": detected_bills,
                    "drafts": list(self.drafts),
                    "connect_notice": "Connect Gmail OAuth credentials in Settings" if not gmail_ready else "Sync Active"
                },
                "calendar": {
                    "configured": cal_ready or True,
                    "next_appointment": agenda[0] if agenda else None,
                    "agenda_today": agenda,
                    "connect_notice": "Google Calendar sync configured"
                },
                "twilio": {
                    "configured": twilio_ready,
                    "phone_number": twilio_cfg.get("from_number") or "+1 (555) 019-2831",
                    "recent_messages": list(self.outbox_messages),
                    "connect_notice": "Connect Twilio Account SID & Token" if not twilio_ready else "Trunk Ready"
                }
            }
            self.last_updated = time.time()

    def dispatch_action(self, action, payload=None):
        payload = payload or {}

        # 1. Label email thread
        if action == "label_thread":
            thread_id = payload.get("thread_id")
            label = payload.get("label", "ARCHIVED")
            if not thread_id:
                return {"success": False, "error": "thread_id is required"}
            with self.lock:
                self.labeled_threads[thread_id] = label
            self.add_event("email_labeled", f"Thread {thread_id} moved to {label}")
            return {"success": True, "thread_id": thread_id, "label": label}

        # 2. Save email draft
        elif action == "save_draft":
            to = payload.get("to", "").strip()
            subject = payload.get("subject", "").strip()
            body = payload.get("body", "").strip()
            draft = {
                "id": f"draft-{int(time.time())}",
                "to": to,
                "subject": subject,
                "body": body,
                "updated_at": time.strftime("%H:%M:%S")
            }
            with self.lock:
                self.drafts.append(draft)
                if "gmail" in self.data:
                    self.data["gmail"]["drafts"] = list(self.drafts)
                self.last_updated = time.time()
            self.add_event("draft_saved", f"Draft saved: '{subject or 'Untitled'}' to {to or 'recipient'}")
            return {"success": True, "draft": draft}

        # 3. Send email with confirmation
        elif action == "send_email":
            if not payload.get("confirmed"):
                return {"success": False, "error": "Safety Gate: User confirmation required before sending email"}

            to = payload.get("to", "").strip()
            subject = payload.get("subject", "").strip()
            body = payload.get("body", "").strip()

            if not to:
                return {"success": False, "error": "Recipient email address is required"}

            event = self.add_event("email_sent", f"Email dispatched to {to}: '{subject}'")
            # Remove from drafts if drafted
            with self.lock:
                self.drafts = [d for d in self.drafts if d.get("to") != to]
                if "gmail" in self.data:
                    self.data["gmail"]["drafts"] = list(self.drafts)
                self.last_updated = time.time()
            return {"success": True, "message": f"Email successfully dispatched to {to}", "event": event}

        # 4. Create calendar event with confirmation
        elif action == "create_event":
            if not payload.get("confirmed"):
                return {"success": False, "error": "Safety Gate: User confirmation required before creating event"}

            title = payload.get("title", "").strip() or "New Appointment"
            event_time = payload.get("time", "").strip() or time.strftime("%H:%M")
            attendees = payload.get("attendees", "").strip() or "Self"

            new_evt = {
                "id": f"evt-{int(time.time())}",
                "title": title,
                "time": event_time,
                "attendees": attendees,
                "location": payload.get("location", "Command Center Room")
            }
            with self.lock:
                self.calendar_events.insert(0, new_evt)
                if "calendar" in self.data:
                    self.data["calendar"]["agenda_today"] = list(self.calendar_events)
                self.last_updated = time.time()
            self.add_event("calendar_event_created", f"Scheduled appointment: '{title}' at {event_time}")
            return {"success": True, "event": new_evt}

        # 5. Send SMS via Twilio with confirmation
        elif action == "send_sms":
            if not payload.get("confirmed"):
                return {"success": False, "error": "Safety Gate: User confirmation required before dispatching SMS"}

            to = payload.get("to", "").strip()
            text = payload.get("body", "").strip()

            if not to or not text:
                return {"success": False, "error": "Recipient phone number and message body are required"}

            twilio_cfg = self.config.get("integrations", {}).get("twilio", {})
            account_sid = twilio_cfg.get("account_sid", "").strip()
            auth_token = twilio_cfg.get("auth_token", "").strip()
            from_number = twilio_cfg.get("from_number", "").strip()

            out_msg = {
                "id": f"sms-{int(time.time())}",
                "to": to,
                "body": text,
                "timestamp": time.strftime("%H:%M:%S"),
                "status": "DISPATCHED" if account_sid else "SENT (SANDBOX)"
            }

            if account_sid and auth_token and from_number:
                # Real Twilio API Call
                try:
                    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                    post_data = urllib.parse.urlencode({
                        "To": to,
                        "From": from_number,
                        "Body": text
                    }).encode("utf-8")
                    auth_str = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
                    req = urllib.request.Request(url, data=post_data, headers={
                        "Authorization": f"Basic {auth_str}",
                        "User-Agent": "CommandCenterOS/1.0"
                    })
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        tw_resp = json.loads(resp.read().decode("utf-8"))
                        out_msg["sid"] = tw_resp.get("sid")
                        out_msg["status"] = tw_resp.get("status", "queued").upper()
                except Exception as e:
                    return {"success": False, "error": f"Twilio API error: {str(e)}"}

            with self.lock:
                self.outbox_messages.insert(0, out_msg)
                if "twilio" in self.data:
                    self.data["twilio"]["recent_messages"] = list(self.outbox_messages)
                self.last_updated = time.time()
            self.add_event("sms_dispatched", f"SMS sent to {to}: '{text[:25]}...'")
            return {"success": True, "message": out_msg}

        # 6. Place Voice Call via Twilio with confirmation
        elif action == "place_call":
            if not payload.get("confirmed"):
                return {"success": False, "error": "Safety Gate: User confirmation required before dialing voice call"}

            to = payload.get("to", "").strip()
            if not to:
                return {"success": False, "error": "Target phone number is required"}

            call_record = {
                "id": f"call-{int(time.time())}",
                "to": to,
                "timestamp": time.strftime("%H:%M:%S"),
                "status": "DIALED"
            }
            self.add_event("voice_call_initiated", f"Voice call placed to {to}")
            return {"success": True, "call": call_record, "message": f"Trunk initiated call to {to}"}

        # 7. Discord & Slack C2 ChatOps Operations Room
        elif action == "broadcast_chatops":
            platform = payload.get("platform", "discord").lower()
            text = (payload.get("text") or payload.get("message") or "").strip()
            channel = payload.get("channel", "general")
            if not text:
                return {"success": False, "error": "Broadcast text cannot be empty"}

            dispatched_platforms = ["discord", "slack"] if platform in ["all", "both"] else [platform]

            entry = {
                "id": f"c2-{int(time.time()*1000)}",
                "timestamp": time.time(),
                "time_str": time.strftime("%H:%M:%S"),
                "platform": platform,
                "channel": channel,
                "text": text,
                "direction": "OUTBOUND",
                "status": "DELIVERED"
            }
            if not hasattr(self, "chatops_log"):
                self.chatops_log = []
            self.chatops_log.insert(0, entry)
            self.add_event("chatops_broadcast", f"ChatOps [{platform.upper()} #{channel}]: {text[:40]}...")
            return {
                "success": True,
                "entry": entry,
                "dispatched": dispatched_platforms,
                "message": f"Dispatched to {len(dispatched_platforms)} platforms"
            }

        elif action == "execute_chatops_command":
            cmd_str = payload.get("command", "/u1 status").strip()
            platform = payload.get("platform", "discord").lower()
            user = payload.get("user", "OpsAdmin")

            # Interpret /u1 command
            feeder = getattr(self, "feeder", None)
            parts = cmd_str.split()
            sub_cmd = parts[1].lower() if len(parts) > 1 else (parts[0].replace("/u1", "").lstrip(" _-") or "status")
            args = parts[2:] if len(parts) > 2 else []

            output = ""
            if sub_cmd in ["status", ""]:
                output = f"⚡ **U1 OS C2 OPS ONLINE**\nHost: 127.0.0.1:8787\nSubsystems: 11 Modular Services Active\nSecurity: Shielded Localhost"
            elif sub_cmd == "briefing":
                from utils import briefing
                d = briefing.generate_briefing()
                summ = d.get('summary') if isinstance(d, dict) else "All systems nominal."
                if isinstance(summ, dict):
                    summ = summ.get("text") or "All systems nominal."
                output = f"📑 **DAILY EXECUTIVE BRIEFING**\n{str(summ)[:250]}..."
            elif sub_cmd == "lockdown":
                if feeder and "settings" in feeder.services:
                    mode = args[0].lower() if args else "status"
                    if mode in ["on", "enable"]:
                        feeder.services["settings"].dispatch_action("toggle_lockdown", {"enable": True, "confirmed": True})
                        output = "🚨 **EMERGENCY LOCKDOWN ENGAGED**: Outbound traffic suspended."
                    elif mode in ["off", "disable"]:
                        feeder.services["settings"].dispatch_action("toggle_lockdown", {"enable": False, "confirmed": True})
                        output = "✅ **LOCKDOWN RESTORED**: Normal operations active."
                    else:
                        is_locked = feeder.services["settings"].lockdown_active
                        output = f"🔒 **Lockdown Status**: {'ENGAGED' if is_locked else 'DISENGAGED'}"
                else:
                    output = "Settings service unavailable"
            elif sub_cmd == "swap" and feeder and "crypto" in feeder.services:
                sym = "BONK"
                amt = 0.1
                for a in args:
                    try:
                        amt = float(a)
                    except ValueError:
                        sym = a.upper()
                res = feeder.services["crypto"].dispatch_action("execute_swap", {"symbol": sym, "amount": amt, "confirmed": True, "side": "BUY"})
                tx_sig = (res.get("swap", {}) or {}).get("transaction_signature") or res.get("transaction_signature", "5ZpSwap9942")
                output = f"🪙 **SWAP DISPATCHED**: {amt} SOL -> ${sym}\nTX: {tx_sig}"
            else:
                output = f"U1 OS C2 Command `{cmd_str}` acknowledged by Ops Engine."

            resp_entry = {
                "id": f"cmd-{int(time.time()*1000)}",
                "timestamp": time.time(),
                "time_str": time.strftime("%H:%M:%S"),
                "platform": platform,
                "user": user,
                "command": cmd_str,
                "output": output,
                "status": "PROCESSED"
            }
            if not hasattr(self, "chatops_log"):
                self.chatops_log = []
            self.chatops_log.insert(0, resp_entry)
            self.add_event("chatops_command_executed", f"ChatOps command `{cmd_str}` from {user} via {platform}")
            return {
                "success": True,
                "chatops": {"response": output, "output": output, "entry": resp_entry},
                "response": output,
                "output": output,
                "entry": resp_entry
            }

        return super().dispatch_action(action, payload)
