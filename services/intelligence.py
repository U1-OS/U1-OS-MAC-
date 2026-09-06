import time
import os
import subprocess
import urllib.request
import json
import xml.etree.ElementTree as ET
from services.base import BaseService

class IntelligenceService(BaseService):
    def __init__(self, config):
        super().__init__("intelligence", config)
        self.configured = True
        self.status = "active"
        self._last_weather_fetch = 0
        self._last_news_fetch = 0
        self.weather_cache = {
            "temp_c": 19,
            "temp_f": 66,
            "condition": "Clear",
            "humidity": "55%",
            "wind": "11 km/h",
            "city": "Sydney",
            "feels_like": "19°C"
        }
        self.news_cache = [
            {"title": "Command Center OS initialized — all systems nominal", "source": "SYSTEM", "url": "#"},
            {"title": "Global financial markets steady amid rate outlook", "source": "FINANCE", "url": "#"},
            {"title": "OpenAI & Anthropic advance frontier agent architectures", "source": "TECH", "url": "#"}
        ]
        self.pool_cache = {
            "configured": False,
            "temp_c": None,
            "temp_f": None,
            "status_text": "SENSOR UNPAIRED: CONNECT SENSOR"
        }

    def _fetch_weather(self):
        now = time.time()
        # Fetch weather every 5 minutes (300s) to avoid rate limits
        if now - self._last_weather_fetch < 300 and self._last_weather_fetch > 0:
            return self.weather_cache

        intel_cfg = self.config.get("intelligence", {})
        city = intel_cfg.get("weather_city", "")
        url = f"https://wttr.in/{city}?format=j1" if city else "https://wttr.in/?format=j1"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "CommandCenterOS/1.0 (Darwin; macOS)"}
            )
            with urllib.request.urlopen(req, timeout=2.5) as response:
                if response.status == 200:
                    raw = json.loads(response.read().decode("utf-8"))
                    curr = raw.get("current_condition", [{}])[0]
                    nearest = raw.get("nearest_area", [{}])[0]
                    area_name = city or nearest.get("areaName", [{}])[0].get("value", "Local")

                    old_temp = self.weather_cache.get("temp_c")
                    new_temp = int(curr.get("temp_C", 20))

                    self.weather_cache = {
                        "temp_c": new_temp,
                        "temp_f": int(curr.get("temp_F", 68)),
                        "condition": curr.get("weatherDesc", [{}])[0].get("value", "Partly Cloudy"),
                        "humidity": f"{curr.get('humidity', '50')}%",
                        "wind": f"{curr.get('windspeedKmph', '10')} km/h",
                        "city": area_name,
                        "feels_like": f"{curr.get('FeelsLikeC', new_temp)}°C"
                    }
                    self._last_weather_fetch = now

                    if old_temp is not None and old_temp != new_temp:
                        self.add_event("weather_shift", f"Weather update: {area_name} {new_temp}°C ({self.weather_cache['condition']})")
        except Exception as e:
            # Keep existing cache on network failure
            pass

        return self.weather_cache

    def _fetch_news(self):
        now = time.time()
        # Fetch news every 10 minutes
        if now - self._last_news_fetch < 600 and self._last_news_fetch > 0:
            return self.news_cache

        headlines = []
        feeds = self.config.get("intelligence", {}).get("news_feeds", [
            "https://news.ycombinator.com/rss"
        ])

        for feed_url in feeds[:2]:
            try:
                req = urllib.request.Request(
                    feed_url,
                    headers={"User-Agent": "CommandCenterOS/1.0"}
                )
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    if resp.status == 200:
                        content = resp.read()
                        root = ET.fromstring(content)
                        # RSS item elements
                        for item in root.findall(".//item")[:5]:
                            title_elem = item.find("title")
                            link_elem = item.find("link")
                            if title_elem is not None and title_elem.text:
                                source = "TECH" if "ycombinator" in feed_url else "NEWS"
                                headlines.append({
                                    "title": title_elem.text.strip(),
                                    "source": source,
                                    "url": link_elem.text.strip() if link_elem is not None and link_elem.text else "#"
                                })
            except Exception:
                continue

        if headlines:
            self.news_cache = headlines
            self._last_news_fetch = now
            self.add_event("news_refresh", f"Intelligence strip updated: {len(headlines)} headlines active")

        return self.news_cache

    def _get_system_telemetry(self):
        load_avg = [0.0, 0.0, 0.0]
        try:
            load_avg = list(os.getloadavg())
        except Exception:
            pass

        uptime_str = "Up"
        try:
            res = subprocess.run(["uptime"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                uptime_str = res.stdout.strip().split("up ")[-1].split(",")[0].strip()
        except Exception:
            pass

        return {
            "load_1m": round(load_avg[0], 2),
            "load_5m": round(load_avg[1], 2),
            "load_15m": round(load_avg[2], 2),
            "uptime": uptime_str,
            "server_time": time.strftime("%H:%M:%S"),
            "server_date": time.strftime("%A, %b %d")
        }

    def _check_pool_sensor(self):
        pool_url = self.config.get("intelligence", {}).get("pool_sensor_url", "").strip()
        if not pool_url:
            return {
                "configured": False,
                "temp_c": None,
                "temp_f": None,
                "status_text": "POOL: CONNECT SENSOR",
                "notice": "Configure pool_sensor_url in config.json"
            }
        try:
            req = urllib.request.Request(pool_url, headers={"User-Agent": "CommandCenterOS/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "configured": True,
                    "temp_c": data.get("temp_c", 26.5),
                    "temp_f": data.get("temp_f", 79.7),
                    "status_text": f"POOL: {data.get('temp_c')}°C",
                    "notice": "Sensor live"
                }
        except Exception:
            return {
                "configured": False,
                "temp_c": None,
                "temp_f": None,
                "status_text": "POOL: UNREACHABLE",
                "notice": "Sensor offline or timeout"
            }

    def poll(self):
        weather = self._fetch_weather()
        news = self._fetch_news()
        telemetry = self._get_system_telemetry()
        pool = self._check_pool_sensor()

        with self.lock:
            self.data = {
                "weather": weather,
                "news": news,
                "telemetry": telemetry,
                "pool": pool
            }
            self.last_updated = time.time()
            self.configured = True
            self.status = "active"

    def dispatch_action(self, action, payload=None):
        if action == "refresh_news":
            self._last_news_fetch = 0
            self._fetch_news()
            return {"success": True, "message": "News ticker refreshed"}
        elif action == "refresh_weather":
            self._last_weather_fetch = 0
            self._fetch_weather()
            return {"success": True, "message": "Weather data refreshed"}
        return super().dispatch_action(action, payload)
