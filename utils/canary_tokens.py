"""
Canary Token & Honeypot Intrusion Trap Sentinel.
Deploys honeypots, fake credentials, canary webhooks, and decoy files to detect,
log, and auto-contain unauthorized intrusions and exfiltration attempts.
"""

import os
import time
import json
import secrets
import hashlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANARY_STORE_PATH = os.path.join(BASE_DIR, "vault", "canary_sentinel.json")
DECOY_FILE_PATH = os.path.join(BASE_DIR, "vault", ".decoy_admin_keys.env")


def _ensure_canary_store() -> dict:
    os.makedirs(os.path.dirname(CANARY_STORE_PATH), exist_ok=True)
    if not os.path.exists(CANARY_STORE_PATH):
        # Create default canary assets
        default_tokens = [
            {
                "token_id": "canary-api-01",
                "type": "API_KEY",
                "label": "Fake Production Stripe Secret Key",
                "token_value": "sk_live_canary_" + secrets.token_hex(16),
                "created_at": int(time.time()),
                "trigger_count": 0,
                "memo": "Seeded in faux-config to detect unauthorized repo inspection",
                "active": True
            },
            {
                "token_id": "canary-webhook-02",
                "type": "WEBHOOK_URL",
                "label": "Decoy Internal Ops Webhook",
                "token_value": "whk_trap_" + secrets.token_hex(12),
                "created_at": int(time.time()),
                "trigger_count": 0,
                "memo": "Decoy webhook in dev documentation",
                "active": True
            },
            {
                "token_id": "canary-db-03",
                "type": "DB_CREDENTIAL",
                "label": "Decoy Read-Only Database Role",
                "token_value": "postgres://honey_audit:" + secrets.token_hex(10) + "@127.0.0.1:5432/main",
                "created_at": int(time.time()),
                "trigger_count": 0,
                "memo": "Decoy DB connection string",
                "active": True
            }
        ]
        
        # Write decoy file
        if not os.path.exists(DECOY_FILE_PATH):
            with open(DECOY_FILE_PATH, "w") as f:
                f.write(f"# DECOY ENCLAVE SECRETS\nSTRIPE_SECRET={default_tokens[0]['token_value']}\nDATABASE_URL={default_tokens[2]['token_value']}\n")

        initial_state = {
            "tokens": default_tokens,
            "alerts": [],
            "decoy_files": [
                {
                    "path": DECOY_FILE_PATH,
                    "expected_sha256": hashlib.sha256(open(DECOY_FILE_PATH, "rb").read()).hexdigest(),
                    "last_checked": int(time.time()),
                    "status": "UNTOUCHED"
                }
            ]
        }
        with open(CANARY_STORE_PATH, "w") as f:
            json.dump(initial_state, f, indent=2)
        return initial_state

    try:
        with open(CANARY_STORE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"tokens": [], "alerts": [], "decoy_files": []}


def _save_canary_store(data: dict):
    os.makedirs(os.path.dirname(CANARY_STORE_PATH), exist_ok=True)
    with open(CANARY_STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def generate_canary_token(token_type: str = "API_KEY", label: str = "Custom Canary Trap", memo: str = "") -> dict:
    """Generate and deploy a new canary token / honeypot asset."""
    store = _ensure_canary_store()
    token_id = f"canary-{token_type.lower()[:3]}-{secrets.token_hex(4)}"
    
    if token_type.upper() == "API_KEY":
        val = f"u1_live_canary_{secrets.token_hex(16)}"
    elif token_type.upper() == "WEBHOOK_URL":
        val = f"/api/canary/trap/{secrets.token_hex(12)}"
    elif token_type.upper() == "DB_CREDENTIAL":
        val = f"u1_honey_db_{secrets.token_hex(8)}"
    else:
        val = f"honey_trap_{secrets.token_hex(16)}"

    token = {
        "token_id": token_id,
        "type": token_type.upper(),
        "label": label,
        "token_value": val,
        "created_at": int(time.time()),
        "trigger_count": 0,
        "memo": memo,
        "active": True
    }

    store["tokens"].insert(0, token)
    _save_canary_store(store)
    return {"success": True, "token": token, "message": f"Canary token '{label}' armed."}


def trigger_canary(token_identifier: str, source_ip: str = "127.0.0.1", user_agent: str = "Unknown", context: dict = None) -> dict:
    """
    Tripwire execution: called when a decoy token, credential, or webhook is accessed.
    Generates high-priority intrusion alert.
    """
    store = _ensure_canary_store()
    matched_token = None

    for t in store.get("tokens", []):
        if t.get("token_id") == token_identifier or t.get("token_value") == token_identifier:
            matched_token = t
            t["trigger_count"] = t.get("trigger_count", 0) + 1
            break

    alert_id = f"alert-canary-{secrets.token_hex(4)}"
    alert = {
        "alert_id": alert_id,
        "timestamp": int(time.time()),
        "severity": "CRITICAL",
        "token_id": matched_token.get("token_id") if matched_token else "UNKNOWN_TRAP",
        "token_label": matched_token.get("label") if matched_token else "Unknown Decoy",
        "token_type": matched_token.get("type") if matched_token else "HONEYPOT_HIT",
        "source_ip": source_ip,
        "user_agent": user_agent,
        "context": context or {},
        "status": "TRIPPED_ACTIVE",
        "containment_action": "PERIMETER_LOCKDOWN_SIGNALED"
    }

    store["alerts"].insert(0, alert)
    store["alerts"] = store["alerts"][:100]
    _save_canary_store(store)

    return {
        "success": True,
        "alert": alert,
        "status": "INTRUSION_DETECTED",
        "message": f"CRITICAL: Canary honeypot trap tripped by IP {source_ip}!"
    }


def list_canary_tokens() -> list:
    """Return all active canary tokens and trap assets."""
    store = _ensure_canary_store()
    return store.get("tokens", [])


def get_intrusion_alerts() -> list:
    """Return all historical intrusion alerts triggered by canary sentinels."""
    store = _ensure_canary_store()
    return store.get("alerts", [])


def clear_canary_alert(alert_id: str) -> dict:
    """Dismiss or resolve an intrusion alert."""
    store = _ensure_canary_store()
    orig_len = len(store.get("alerts", []))
    store["alerts"] = [a for a in store.get("alerts", []) if a.get("alert_id") != alert_id]
    _save_canary_store(store)
    cleared = orig_len > len(store.get("alerts", []))
    return {"success": cleared, "alert_id": alert_id, "message": "Alert resolved." if cleared else "Alert not found."}


def check_honeyfile_integrity() -> dict:
    """Check if decoy honeypot files in vault have been modified or tampered with."""
    store = _ensure_canary_store()
    decoy_status = []
    has_tamper = False

    for decoy in store.get("decoy_files", []):
        path = decoy.get("path")
        if os.path.exists(path):
            current_hash = hashlib.sha256(open(path, "rb").read()).hexdigest()
            tampered = current_hash != decoy.get("expected_sha256")
            if tampered:
                has_tamper = True
                decoy["status"] = "TAMPERED_INTRUSION"
                # Trigger alarm
                trigger_canary(f"honeyfile-{os.path.basename(path)}", source_ip="localhost", context={"file": path, "hash": current_hash})
            else:
                decoy["status"] = "UNTOUCHED"
            decoy["last_checked"] = int(time.time())
            decoy_status.append(decoy)

    _save_canary_store(store)
    return {"success": True, "tamper_detected": has_tamper, "decoys": decoy_status}
