"""Account setup catalog. Saving settings does not authorize or test an account."""
import copy
import json
import os
import platform
import secrets
import shutil
import sys
import tempfile

CSRF_TOKEN = secrets.token_urlsafe(32)


def entry(key, name, group, fields, portal, note, stage="installed"):
    return dict(id=key, name=name, category=group, fields=[
        dict(id=f, label=f.replace("_", " ").title(), secret=any(
            word in f for word in ("key", "secret", "token")) and not f.endswith("_path"))
        for f in fields], portal=portal, note=note, stage=stage)


CATALOG = [
    entry("gmail", "Gmail", "Communication", ["client_id", "client_secret", "refresh_token"], "https://console.cloud.google.com/apis/credentials", "Add your Google OAuth credentials when you are ready."),
    entry("google_calendar", "Google Calendar", "Communication", ["calendar_id"], "https://calendar.google.com/", "Uses the Google credentials saved under Gmail. Saving a calendar ID alone does not authenticate Google."),
    entry("twilio", "Twilio SMS and calls", "Communication", ["account_sid", "auth_token", "from_number"], "https://console.twilio.com/", "Account details and a provisioned sending number are required."),
    entry("stripe", "Stripe", "Finance", ["secret_key", "currency"], "https://dashboard.stripe.com/apikeys", "Use a restricted key with the permissions you need."),
    entry("openai", "OpenAI", "AI and media", ["api_key"], "https://platform.openai.com/api-keys", "API billing and credentials are separate from a chat subscription."),
    entry("anthropic", "Anthropic", "AI and media", ["api_key"], "https://console.anthropic.com/", "Configure API access later in your provider account."),
    entry("canva", "Canva", "AI and media", ["api_key"], "https://www.canva.com/developers/", "The recovered app includes a draft design adapter; production OAuth integration remains unfinished.", "setup_slot"),
    entry("elevenlabs", "ElevenLabs", "AI and media", ["api_key"], "https://elevenlabs.io/", "Voice generation requires a provider account."),
    entry("pexels", "Pexels", "AI and media", ["api_key"], "https://www.pexels.com/api/", "Stock media access can be configured later."),
    entry("ollama", "Ollama local AI", "AI and media", [], "https://ollama.com/download", "The app adapter is included. A local Ollama runtime and downloaded model are separate prerequisites."),
    entry("hibp", "Have I Been Pwned", "Research", ["api_key"], "https://haveibeenpwned.com/API/Key", "Authenticated breach lookups require your own API access."),
    entry("steamworks", "Steamworks", "Publishing", ["app_id", "publisher_key"], "https://partner.steamgames.com/", "Publisher account setup is deferred."),
    entry("app_store_connect", "App Store Connect", "Publishing", ["issuer_id", "key_id", "private_key_path"], "https://appstoreconnect.apple.com/", "Reference your signing key file locally when configuring publishing."),
    entry("solana", "Solana RPC", "Crypto", ["rpc_url", "wallet_address"], "https://solana.com/", "RPC helper files are installed. Wallet connection and live holdings wiring are pending.", "adapter_files"),
    entry("jupiter", "Jupiter swaps", "Crypto", ["api_key"], "https://portal.jup.ag/", "Unfinished Antigravity adapter. Requires migration to the current API before activation.", "adapter_files"),
    entry("twitter", "Twitter / X", "Crypto", ["bearer_token"], "https://developer.x.com/", "Credential storage only. Official API account integration is not implemented.", "setup_slot"),
    entry("nitter", "Nitter RSS", "Crypto", ["instance_url"], "https://github.com/zedeus/nitter", "RSS helper files are installed; instance availability and live wiring remain unverified.", "adapter_files"),
    entry("birdeye", "Birdeye history", "Crypto", ["api_key"], "https://birdeye.so/", "Historical data integration is pending. No synthetic backtest results are presented as real.", "setup_slot"),
]
BY_ID = {item["id"]: item for item in CATALOG}


def catalog(config, root):
    cards = []
    settings = config.get("integrations", {})
    for item in CATALOG:
        card = copy.deepcopy(item)
        values = settings.get(item["id"], {})
        if not isinstance(values, dict):
            values = {}
        saved = 0
        for field in card["fields"]:
            value = str(values.get(field["id"], "") or "")
            field["saved"] = bool(value)
            field["value"] = "" if field["secret"] else value
            saved += bool(value)
        card["status"] = "settings_saved" if saved else "not_configured"
        card["saved_fields"] = saved
        cards.append(card)
    return dict(success=True, csrf_token=CSRF_TOKEN, installation_root=root,
                cards=cards, runtime=dict(python=sys.version.split()[0],
                platform=platform.platform(), ffmpeg=bool(shutil.which("ffmpeg")),
                ollama=bool(shutil.which("ollama"))),
                setup_mode=config.get("system", {}).get("setup_mode", True))


def updated_config(config, payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    key = payload.get("integration")
    if key not in BY_ID:
        raise ValueError("Unknown integration")
    values = payload.get("values", {})
    if not isinstance(values, dict):
        raise ValueError("Expected settings as an object")
    fields = {field["id"]: field for field in BY_ID[key]["fields"]}
    if set(values) - set(fields):
        raise ValueError("Unknown settings field")
    result = copy.deepcopy(config)
    dest = result.setdefault("integrations", {}).setdefault(key, {})
    if payload.get("clear") is True:
        result["integrations"][key] = {}
        return result
    for field, value in values.items():
        if not isinstance(value, str) or len(value) > 8192:
            raise ValueError("Settings must be text up to 8192 characters")
        value = value.strip()
        if fields[field]["secret"] and not value:
            continue  # An empty password field preserves the saved secret.
        if "\u2022" in value:
            raise ValueError("Enter the actual credential, not a masked value")
        dest[field] = value
    return result


def persist(config, filename):
    """Atomic, owner-only local storage. This file is not encrypted."""
    fd, tmp = tempfile.mkstemp(prefix=".config-", dir=os.path.dirname(filename))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, filename)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
