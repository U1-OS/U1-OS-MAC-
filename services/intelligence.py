import time
import os
import subprocess
import urllib.request
import json
import math
import hashlib
import threading
import urllib.parse
import xml.etree.ElementTree as ET
from services.base import BaseService
from utils import news_markets

class IntelligenceService(BaseService):
    def __init__(self, config):
        super().__init__("intelligence", config)
        self.configured = False
        self.status = "unavailable"
        self._last_weather_fetch = 0
        self._last_news_fetch = 0
        self._weather_attempted_at = 0
        self._news_attempted_at = 0
        self._weather_city = None
        self._news_feed_key = None
        self._weather_lock = threading.Lock()
        self._news_lock = threading.Lock()
        self.weather_cache = self._empty_weather()
        self.news_cache = []
        self.news_status = {"success": False, "stale": False, "source": None,
                            "fetched_at": None, "error": "News has not been received."}
        self.pool_cache = {"configured": False, "temp_c": None, "temp_f": None,
                           "status_text": "SENSOR UNPAIRED: CONNECT SENSOR"}

    @staticmethod
    def _empty_weather(city=None):
        return {"success": False, "stale": False, "temp_c": None, "temp_f": None,
                "condition": None, "humidity": None, "wind": None, "city": city or None,
                "feels_like": None, "source": "wttr.in", "source_url": "https://wttr.in/",
                "fetched_at": None, "observed_at": None, "timezone": None,
                "error": "Weather has not been received."}

    @staticmethod
    def _number(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError, OverflowError):
            return None

    def _fetch_weather(self):
        with self._weather_lock:
            now = time.time()
            city = str(self.config.get("intelligence", {}).get("weather_city", "")).strip()[:100]
            if city != self._weather_city:
                self._weather_city = city
                self.weather_cache = self._empty_weather(city)
                self._weather_attempted_at = 0
            ttl = 300 if self.weather_cache.get("success") else 60
            if self._weather_attempted_at and now - self._weather_attempted_at < ttl:
                return dict(self.weather_cache)
            self._weather_attempted_at = now
            try:
                url = "https://wttr.in/" + urllib.parse.quote(city, safe="") + "?format=j1"
                raw = json.loads(news_markets.fetch(url))
                current = raw.get("current_condition", [])[0]
                temperature = self._number(current.get("temp_C"))
                descriptions = current.get("weatherDesc") or []
                condition = descriptions[0].get("value") if descriptions else None
                if temperature is None or not isinstance(condition, str) or not condition.strip():
                    raise ValueError("Weather measurements are incomplete")
                areas = raw.get("nearest_area") or []
                names = areas[0].get("areaName", []) if areas else []
                area = names[0].get("value") if names else None
                humidity = self._number(current.get("humidity"))
                wind = self._number(current.get("windspeedKmph"))
                feels = self._number(current.get("FeelsLikeC"))
                observed = current.get("localObsDateTime") or current.get("observation_time")
                fetched = time.time()
                self.weather_cache = {
                    "success": True, "stale": False, "temp_c": temperature,
                    "temp_f": self._number(current.get("temp_F")), "condition": condition.strip()[:120],
                    "humidity": f"{humidity:g}%" if humidity is not None else None,
                    "wind": f"{wind:g} km/h" if wind is not None else None,
                    "city": city or (area[:100] if isinstance(area, str) else None),
                    "feels_like": f"{feels:g} C" if feels is not None else None,
                    "source": "wttr.in", "source_url": "https://wttr.in/",
                    "observed_at": observed[:80] if isinstance(observed, str) else None,
                    "timezone": None, "fetched_at": fetched, "attempted_at": now,
                    "refresh_seconds": 300, "error": None,
                    "notice": "Provider snapshot; retrieval time is not the observation time. "
                              "The provider timezone is not inferred."
                }
                self._last_weather_fetch = fetched
            except Exception:
                self.weather_cache = {**self.weather_cache, "success": False,
                    "stale": bool(self.weather_cache.get("fetched_at")), "attempted_at": now,
                    "refresh_seconds": 60,
                    "error": "Weather unavailable. Retained measurements, if any, are stale."}
            return dict(self.weather_cache)

    def _fetch_news(self):
        with self._news_lock:
            now = time.time()
            feeds = self.config.get("intelligence", {}).get("news_feeds", ["https://news.ycombinator.com/rss"])
            key = tuple(feeds) if isinstance(feeds, list) and all(isinstance(feed, str) for feed in feeds) else None
            if key != self._news_feed_key:
                self._news_feed_key = key
                self.news_cache = []
                self.news_status = {"success": False, "stale": False, "fetched_at": None}
                self._news_attempted_at = 0
            ttl = 600 if self.news_status.get("success") else 60
            if self._news_attempted_at and now - self._news_attempted_at < ttl:
                return list(self.news_cache)
            self._news_attempted_at = now
            try:
                known = {spec[1]: category for category, spec in news_markets.SOURCES.items()}
                if not key or len(key) > 2 or any(url not in known and url != "https://news.ycombinator.com/rss" for url in key):
                    raise ValueError("Unsupported news feed")
                items, seen, fetched_times, sources = [], set(), [], []
                for url in dict.fromkeys(key):
                    if url in known:
                        value = news_markets.news(known[url])
                        if not value.get("success") or value.get("stale"):
                            raise ValueError("Publisher unavailable")
                        rows = value.get("items", [])[:5]
                        fetched = value["fetched_at"]
                        source = value["source"]
                    else:
                        channel = news_markets.rss_channel(news_markets.fetch(url))
                        rows, source = [], "Hacker News"
                        for row in channel.findall("item")[:10]:
                            title = (row.findtext("title") or "").strip()[:400]
                            link = news_markets.safe_story_url((row.findtext("link") or "").strip())
                            if title and link:
                                rows.append({"id": hashlib.sha256(link.encode()).hexdigest()[:24],
                                    "title": title, "url": link, "source": source,
                                    "published_at": news_markets.published_time(row.findtext("pubDate"))})
                        rows = rows[:5]
                        fetched = time.time()
                    sources.append(source)
                    fetched_times.append(fetched)
                    for item in rows:
                        if item["url"] not in seen:
                            seen.add(item["url"])
                            items.append({**item, "stale": False, "fetched_at": fetched})
                self.news_cache = items
                self._last_news_fetch = min(fetched_times)
                self.news_status = {"success": True, "stale": False, "source": " / ".join(sources),
                    "source_urls": list(dict.fromkeys(key)), "fetched_at": self._last_news_fetch,
                    "attempted_at": now, "refresh_seconds": 600, "error": None}
            except Exception:
                self.news_cache = [{**item, "stale": True} for item in self.news_cache]
                self.news_status = {**self.news_status, "success": False,
                    "stale": bool(self.news_status.get("fetched_at")), "attempted_at": now,
                    "refresh_seconds": 60,
                    "error": "News unavailable or feed unsupported. Only the existing fixed publisher feeds are accepted."}
            return list(self.news_cache)

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

    def _get_hardware_telemetry(self):
        import re
        # Battery
        battery_info = {
            "present": False,
            "percent": None,
            "is_ac": True,
            "charging": False,
            "discharging": False,
            "remaining": "AC Connected",
            "status_label": "AC Power"
        }
        try:
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=2)
            out = res.stdout
            if out:
                pct = re.search(r'(\d+)%', out)
                if pct:
                    battery_info["present"] = True
                    battery_info["percent"] = int(pct.group(1))
                battery_info["is_ac"] = "AC Power" in out
                battery_info["discharging"] = bool(re.search(r'\bdischarging\b', out.lower()))
                battery_info["charging"] = bool(re.search(r'\bcharging\b', out.lower())) and not battery_info["discharging"]
                rem = re.search(r'(\d+:\d+)\s+remaining', out)
                if rem:
                    battery_info["remaining"] = f"{rem.group(1)} left"
                elif "charged" in out.lower():
                    battery_info["remaining"] = "Fully Charged"
                elif battery_info["is_ac"]:
                    battery_info["remaining"] = "AC Connected"

                if battery_info["charging"]:
                    battery_info["status_label"] = f"{battery_info['percent']}% ⚡ Charging"
                elif battery_info["discharging"]:
                    battery_info["status_label"] = f"{battery_info['percent']}% ({battery_info['remaining']})"
                elif battery_info["percent"] is not None:
                    battery_info["status_label"] = f"{battery_info['percent']}% AC"
        except Exception:
            pass

        # Disk
        disk_info = {
            "total_gb": 0,
            "free_gb": 0,
            "used_gb": 0,
            "used_pct": 0,
            "mount": "/"
        }
        try:
            s = os.statvfs('/')
            t = (s.f_blocks * s.f_frsize) / (1024**3)
            f = (s.f_bavail * s.f_frsize) / (1024**3)
            u = t - f
            disk_info = {
                "total_gb": round(t, 1),
                "free_gb": round(f, 1),
                "used_gb": round(u, 1),
                "used_pct": round((u / t) * 100, 1) if t > 0 else 0,
                "mount": "/"
            }
        except Exception:
            pass

        # CPU & RAM
        hw_info = {
            "model": "Macintosh",
            "cpu_cores": os.cpu_count() or 8,
            "ram_gb": 16.0
        }
        try:
            m = subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True, timeout=2)
            if m.returncode == 0 and m.stdout.strip():
                hw_info["model"] = m.stdout.strip()
            r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0 and r.stdout.strip():
                hw_info["ram_gb"] = round(int(r.stdout.strip()) / (1024**3), 1)
        except Exception:
            pass

        return {
            "battery": battery_info,
            "disk": disk_info,
            "system": hw_info
        }

    def poll(self):
        weather = self._fetch_weather()
        news = self._fetch_news()
        telemetry = self._get_system_telemetry()
        pool = self._check_pool_sensor()
        hardware = self._get_hardware_telemetry()
        with self.lock:
            ready = weather.get("success") is True and self.news_status.get("success") is True
            self.data = {"weather": weather, "news": news, "news_status": dict(self.news_status),
                         "telemetry": telemetry, "pool": pool, "hardware": hardware,
                         "success": ready, "notice": "Provider availability and freshness are reported per feed."}
            self.last_updated = time.time()
            self.configured = ready
            self.status = "active" if ready else "unavailable"

    def dispatch_action(self, action, payload=None):
        if action == "refresh_news":
            self._fetch_news()
            return {"success": self.news_status.get("success") is True,
                    "stale": self.news_status.get("stale", False),
                    "message": "News snapshot available; cache intervals apply." if self.news_status.get("success")
                               else self.news_status.get("error", "News unavailable.")}
        elif action == "refresh_weather":
            value = self._fetch_weather()
            return {"success": value.get("success") is True, "stale": value.get("stale", False),
                    "message": "Weather snapshot available; cache intervals apply." if value.get("success")
                               else value.get("error", "Weather unavailable.")}
        return super().dispatch_action(action, payload)
