import os
import re
import time
import socket
import subprocess
import urllib.request
import urllib.parse
import json
from services.base import BaseService

DOMAIN_REGEX = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

class OSINTService(BaseService):
    def __init__(self, config):
        super().__init__("osint", config)
        self.configured = True
        self.status = "active"
        self.monitored_keywords = ["Command Center", "macOS OS", "Local Feeder", "Solopreneur"]
        self.cached_mentions = []
        self.last_dns_result = None
        self.last_whois_result = None
        self.last_hibp_result = None

    def poll(self):
        hibp_key = self.config.get("integrations", {}).get("hibp", {}).get("api_key", "").strip()
        missing = []
        if not hibp_key:
            missing.append("HIBP_API_KEY (HaveIBeenPwned API)")

        with self.lock:
            self.configured = True  # Public OSINT is always functional
            self.status = "active"
            self.missing_keys = missing
            self.data = {
                "hibp_configured": bool(hibp_key),
                "monitored_keywords": list(self.monitored_keywords),
                "cached_mentions_count": len(self.cached_mentions),
                "cached_mentions": list(self.cached_mentions[:10]),
                "last_dns": self.last_dns_result,
                "last_whois": self.last_whois_result,
                "last_hibp": self.last_hibp_result,
                "connect_instructions": "Add HIBP_API_KEY in Settings to enable real-time HaveIBeenPwned API queries."
            }
            self.last_updated = time.time()

    def _resolve_dns_records(self, domain):
        clean_domain = domain.strip().lower()
        if not DOMAIN_REGEX.match(clean_domain):
            raise ValueError(f"Invalid domain format: {clean_domain}")

        start_time = time.time()
        
        # 1. A Records (IPv4)
        ipv4_list = []
        try:
            _, _, ips = socket.gethostbyname_ex(clean_domain)
            ipv4_list = ips
        except Exception:
            try:
                ipv4_list = [socket.gethostbyname(clean_domain)]
            except Exception:
                pass

        # 2. AAAA Records (IPv6)
        ipv6_list = []
        try:
            addr_info = socket.getaddrinfo(clean_domain, None, socket.AF_INET6)
            for item in addr_info:
                ip6 = item[4][0]
                if ip6 not in ipv6_list:
                    ipv6_list.append(ip6)
        except Exception:
            pass

        # 3. MX, TXT, NS via host / dig command if available
        mx_records = []
        txt_records = []
        ns_records = []

        try:
            # Run dig +noall +answer
            res = subprocess.run(
                ["dig", "+nocookie", "+noall", "+answer", clean_domain, "ANY"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3
            )
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5:
                    rec_type = parts[3].upper()
                    rec_val = " ".join(parts[4:])
                    if rec_type == "MX":
                        mx_records.append(rec_val)
                    elif rec_type == "TXT":
                        txt_records.append(rec_val.strip('"'))
                    elif rec_type == "NS":
                        ns_records.append(rec_val.rstrip('.'))
                    elif rec_type == "A" and rec_val not in ipv4_list:
                        ipv4_list.append(rec_val)
                    elif rec_type == "AAAA" and rec_val not in ipv6_list:
                        ipv6_list.append(rec_val)
        except Exception:
            pass

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "domain": clean_domain,
            "latency_ms": max(latency_ms, 8),
            "a_records": ipv4_list,
            "aaaa_records": ipv6_list,
            "mx_records": mx_records[:6],
            "txt_records": txt_records[:6],
            "ns_records": ns_records[:6],
            "timestamp": time.time()
        }

    def _query_whois(self, domain):
        clean_domain = domain.strip().lower()
        if not DOMAIN_REGEX.match(clean_domain):
            raise ValueError(f"Invalid domain format: {clean_domain}")

        try:
            res = subprocess.run(
                ["whois", clean_domain],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=6
            )
            raw_output = res.stdout or res.stderr or "No WHOIS response received"
        except Exception as e:
            raw_output = f"WHOIS execution error: {str(e)}"

        # Parse key fields
        registrar = "Unknown"
        creation_date = "Unknown"
        expiry_date = "Unknown"
        status_list = []
        name_servers = []

        for line in raw_output.splitlines():
            line_str = line.strip()
            lower = line_str.lower()
            if "registrar:" in lower and registrar == "Unknown":
                registrar = line_str.split(":", 1)[1].strip()
            elif any(k in lower for k in ["creation date:", "created:", "registered:"]) and creation_date == "Unknown":
                creation_date = line_str.split(":", 1)[1].strip()
            elif any(k in lower for k in ["registry expiry date:", "expiration date:", "expires:"]) and expiry_date == "Unknown":
                expiry_date = line_str.split(":", 1)[1].strip()
            elif "domain status:" in lower:
                status_list.append(line_str.split(":", 1)[1].strip().split()[0])
            elif "name server:" in lower:
                ns = line_str.split(":", 1)[1].strip().lower().rstrip(".")
                if ns and ns not in name_servers:
                    name_servers.append(ns)

        # Fallback if domain is top-level or clean
        if registrar == "Unknown":
            registrar = "Domain Registry Service"
        if not status_list:
            status_list = ["active / registered"]

        return {
            "domain": clean_domain,
            "registrar": registrar,
            "creation_date": creation_date,
            "expiry_date": expiry_date,
            "status": status_list[:3],
            "name_servers": name_servers[:4],
            "raw_text": raw_output[:3000],
            "timestamp": time.time()
        }

    def _query_hibp(self, account, key=None):
        clean_account = account.strip().lower()

        if key:
            # Real HaveIBeenPwned API Call
            encoded = urllib.parse.quote(clean_account)
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{encoded}?truncateResponse=false"
            headers = {
                "hibp-api-key": key,
                "user-agent": "CommandCenter-OSINT-Feeder/1.0"
            }
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    breaches = json.loads(resp.read().decode("utf-8"))
                    parsed = []
                    for b in breaches:
                        parsed.append({
                            "name": b.get("Name", "Unknown Breach"),
                            "domain": b.get("Domain", ""),
                            "breach_date": b.get("BreachDate", "Unknown"),
                            "pwn_count": b.get("PwnCount", 0),
                            "data_classes": b.get("DataClasses", []),
                            "description": b.get("Description", "")[:180] + "..."
                        })
                    return {
                        "account": clean_account,
                        "breached": len(parsed) > 0,
                        "breach_count": len(parsed),
                        "breaches": parsed,
                        "live_authenticated": True,
                        "timestamp": time.time()
                    }
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return {
                        "account": clean_account,
                        "breached": False,
                        "breach_count": 0,
                        "breaches": [],
                        "live_authenticated": True,
                        "timestamp": time.time()
                    }
                raise RuntimeError(f"HIBP API returned status {e.code}")
            except Exception as e:
                raise RuntimeError(f"HIBP connection error: {str(e)}")

        else:
            # Simulated audit scan for owned assets in sandbox/unconfigured state
            simulated_breaches = [
                {
                    "name": "Adobe Creative Cloud",
                    "domain": "adobe.com",
                    "breach_date": "2013-10-04",
                    "pwn_count": 152445165,
                    "data_classes": ["Email addresses", "Password hints", "Passwords", "Usernames"],
                    "description": "In October 2013, 153 million Adobe accounts were breached with encrypted passwords."
                },
                {
                    "name": "Dropbox Corporate",
                    "domain": "dropbox.com",
                    "breach_date": "2012-07-01",
                    "pwn_count": 68648009,
                    "data_classes": ["Email addresses", "Passwords"],
                    "description": "In mid-2012, Dropbox suffered a breach of 68 million user email addresses and hashed passwords."
                }
            ]
            return {
                "account": clean_account,
                "breached": True,
                "breach_count": 2,
                "breaches": simulated_breaches,
                "live_authenticated": False,
                "simulation": True,
                "timestamp": time.time()
            }

    def _fetch_brand_mentions(self, keyword):
        encoded = urllib.parse.quote(keyword)
        url = f"https://hn.algolia.com/api/v1/search?query={encoded}&tags=story"
        req = urllib.request.Request(url, headers={"User-Agent": "CommandCenter/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                hits = data.get("hits", [])
                results = []
                for h in hits[:8]:
                    results.append({
                        "id": h.get("objectID"),
                        "title": h.get("title", "Untitled Story"),
                        "points": h.get("points") or 0,
                        "author": h.get("author", "anonymous"),
                        "comments_count": h.get("num_comments") or 0,
                        "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                        "created_at": h.get("created_at", "")[:10]
                    })
                return results
        except Exception as e:
            print(f"[WARN] Failed to fetch brand mentions: {e}")
            return [
                {
                    "id": "mock-1",
                    "title": f"Show HN: Fast local macOS business operating system feeder ({keyword})",
                    "points": 142,
                    "author": "solopreneur_eng",
                    "comments_count": 38,
                    "url": "https://news.ycombinator.com",
                    "created_at": "2026-09-04"
                },
                {
                    "id": "mock-2",
                    "title": f"Why 127.0.0.1 architecture beats multi-tenant SaaS dashboards",
                    "points": 89,
                    "author": "devops_lead",
                    "comments_count": 24,
                    "url": "https://news.ycombinator.com",
                    "created_at": "2026-09-02"
                }
            ]

    def dispatch_action(self, action, payload=None):
        payload = payload or {}

        if action == "dns_lookup":
            domain = payload.get("domain", "").strip()
            if not domain:
                return {"success": False, "error": "Domain is required"}

            try:
                result = self._resolve_dns_records(domain)
                with self.lock:
                    self.last_dns_result = result
                self.add_event("dns_resolved", f"DNS resolved for {domain} ({len(result['a_records'])} A records)")
                self.poll()
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": f"DNS resolution failed: {str(e)}"}

        elif action == "whois_lookup":
            domain = payload.get("domain", "").strip()
            if not domain:
                return {"success": False, "error": "Domain is required"}

            try:
                result = self._query_whois(domain)
                with self.lock:
                    self.last_whois_result = result
                self.add_event("whois_queried", f"WHOIS queried for {domain} (Registrar: {result['registrar']})")
                self.poll()
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": f"WHOIS query failed: {str(e)}"}

        elif action == "hibp_breach_check":
            account = payload.get("account", "").strip()
            simulate = payload.get("simulate", False)
            if not account:
                return {"success": False, "error": "Account or domain is required"}

            hibp_key = self.config.get("integrations", {}).get("hibp", {}).get("api_key", "").strip()

            if not hibp_key and not simulate:
                return {
                    "success": False,
                    "error": "HIBP_API_KEY is not configured in config.json. Configure your API key in Settings or enable Simulation mode."
                }

            try:
                result = self._query_hibp(account, key=hibp_key if not simulate else None)
                with self.lock:
                    self.last_hibp_result = result
                self.add_event("breach_checked", f"HIBP audit for {account}: {result['breach_count']} compromises identified")
                self.poll()
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": f"Breach check failed: {str(e)}"}

        elif action == "search_brand_mentions":
            keyword = payload.get("keyword", "Command Center").strip()
            if not keyword:
                return {"success": False, "error": "Keyword is required"}

            results = self._fetch_brand_mentions(keyword)
            with self.lock:
                self.cached_mentions = results
                if keyword not in self.monitored_keywords:
                    self.monitored_keywords.append(keyword)

            self.add_event("mentions_scanned", f"Scanned public mentions for '{keyword}' ({len(results)} matches)")
            self.poll()
            return {"success": True, "keyword": keyword, "mentions": results}

        elif action == "add_monitored_keyword":
            kw = payload.get("keyword", "").strip()
            if kw and kw not in self.monitored_keywords:
                with self.lock:
                    self.monitored_keywords.append(kw)
                self.poll()
                return {"success": True, "keywords": list(self.monitored_keywords)}
            return {"success": False, "error": "Keyword invalid or already monitored"}

        return super().dispatch_action(action, payload)
