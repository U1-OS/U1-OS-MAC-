#!/usr/bin/env python3
"""
Command Center — Native Headless Browser Crawler & Web Inspector
Leverages native macOS Google Chrome in headless mode for full JavaScript DOM rendering,
chart snapshot capture, and on-page contract address extraction.
"""

import os
import re
import time
import shutil
import subprocess
import urllib.request
import urllib.parse
from html.parser import HTMLParser

CHROME_DEFAULT_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
]

SOL_CA_REGEX = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')
EVM_CA_REGEX = re.compile(r'\b0x[a-fA-F0-9]{40}\b')

class FastTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_script = False
        self.in_style = False
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True
        elif tag.lower() in ["script", "style", "noscript"]:
            self.in_script = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False
        elif tag.lower() in ["script", "style", "noscript"]:
            self.in_script = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data.strip()
        elif not self.in_script and not self.in_style:
            d = data.strip()
            if d:
                self.text_parts.append(d)

    def get_text(self):
        return " ".join(self.text_parts)

def find_chrome_binary():
    """Detects available Google Chrome or Chromium executable on macOS."""
    for path in CHROME_DEFAULT_PATHS:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    which_chrome = shutil.which("google-chrome") or shutil.which("chromium")
    return which_chrome

def fetch_rendered_dom(url, wait_ms=2500, timeout_sec=15):
    """
    Renders the target URL through native headless Chrome and dumps the full JS DOM.
    Falls back to urllib if Chrome is unavailable.
    """
    chrome_bin = find_chrome_binary()
    t0 = time.time()

    if chrome_bin:
        cmd = [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--dump-dom",
            "--no-sandbox",
            "--disable-logging",
            "--log-level=3",
            f"--virtual-time-budget={wait_ms}",
            url
        ]
        try:
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=timeout_sec, text=True, errors="replace"
            )
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            return {
                "ok": res.returncode == 0 and len(res.stdout) > 0,
                "engine": "chrome_headless",
                "html": res.stdout,
                "latency_ms": elapsed_ms,
                "url": url
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "engine": "chrome_headless", "error": "TIMEOUT", "latency_ms": round((time.time() - t0) * 1000, 1)}
        except Exception as e:
            pass

    # Fallback to standard urllib
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            elapsed_ms = round((time.time() - t0) * 1000, 1)
            return {
                "ok": True,
                "engine": "http_urllib",
                "html": html,
                "latency_ms": elapsed_ms,
                "url": url
            }
    except Exception as e:
        return {
            "ok": False,
            "engine": "fallback",
            "error": str(e),
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "url": url
        }

def capture_screenshot(url, output_path, wait_ms=2500, window_size="1280,800", timeout_sec=15):
    """Takes a headless screenshot of the target URL and saves it to output_path."""
    chrome_bin = find_chrome_binary()
    if not chrome_bin:
        return {"ok": False, "error": "CHROME_NOT_FOUND"}
    
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        f"--screenshot={output_path}",
        f"--window-size={window_size}",
        "--no-sandbox",
        "--disable-logging",
        "--log-level=3",
        f"--virtual-time-budget={wait_ms}",
        url
    ]
    t0 = time.time()
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout_sec)
        ok = res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
        return {
            "ok": ok,
            "path": output_path,
            "size_bytes": os.path.getsize(output_path) if ok else 0,
            "latency_ms": round((time.time() - t0) * 1000, 1)
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def inspect_page(url, wait_ms=2500):
    """
    Crawls URL, parses rendered text, title, and detects crypto contract addresses.
    """
    dom_res = fetch_rendered_dom(url, wait_ms=wait_ms)
    if not dom_res.get("ok"):
        return {
            "ok": False,
            "url": url,
            "error": dom_res.get("error", "Failed to render DOM"),
            "latency_ms": dom_res.get("latency_ms", 0)
        }

    html = dom_res.get("html", "")
    parser = FastTextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass

    raw_text = parser.get_text()
    title = parser.title or "Untitled Page"

    # Contract address extraction
    sol_cas = list(set(SOL_CA_REGEX.findall(html)))
    evm_cas = list(set(EVM_CA_REGEX.findall(html)))

    # Filter common false positives
    known_clean_sol = [ca for ca in sol_cas if len(ca) >= 32 and not ca.startswith("0000")]

    return {
        "ok": True,
        "url": url,
        "engine": dom_res.get("engine"),
        "title": title,
        "text_preview": raw_text[:500] if raw_text else "",
        "word_count": len(raw_text.split()),
        "detected_solana_cas": known_clean_sol[:10],
        "detected_evm_cas": evm_cas[:10],
        "latency_ms": dom_res.get("latency_ms", 0)
    }

def inspect_token_dex(token_ca, dex="photon"):
    """
    Navigates to Photon-SOL or DexScreener to crawl live chart DOM.
    """
    if dex == "dexscreener":
        url = f"https://dexscreener.com/solana/{token_ca}"
    else:
        url = f"https://photon-sol.tinyastro.io/en/lp/{token_ca}"
    return inspect_page(url, wait_ms=3000)
