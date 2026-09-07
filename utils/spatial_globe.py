"""
WebGL 3D Spatial Globe & Orbit Command Deck Telemetry Engine.
Provides spherical mathematical coordinate projections (lat/lon/alt to 3D Cartesian XYZ),
Haversine great-circle flight path calculations, and orbital satellite constellation telemetry.
"""

import os
import time
import json
import math
import secrets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLOBE_STORE_PATH = os.path.join(BASE_DIR, "vault", "spatial_globe.json")

SEED_INTEL_MARKERS = [
    {"name": "San Francisco Primary C2", "lat": 37.7749, "lon": -122.4194, "type": "command_gateway", "threat_level": "none"},
    {"name": "Tokyo High-Speed Enclave", "lat": 35.6762, "lon": 139.6503, "type": "mev_validator", "threat_level": "low"},
    {"name": "London Sovereign Node", "lat": 51.5074, "lon": -0.1278, "type": "relay_bridge", "threat_level": "none"},
    {"name": "Frankfurt ZK Vault", "lat": 50.1109, "lon": 8.6821, "type": "zk_backup", "threat_level": "none"}
]

SEED_SATELLITES = [
    {"sat_id": "SAT-U1-LEO-01", "name": "U1-Orbital-Relay-Alpha", "altitude_km": 540.0, "inclination_deg": 53.2, "velocity_kmh": 27500},
    {"sat_id": "SAT-U1-LEO-02", "name": "U1-Orbital-Relay-Beta", "altitude_km": 560.0, "inclination_deg": 97.4, "velocity_kmh": 27400}
]

def _ensure_globe_store() -> dict:
    os.makedirs(os.path.dirname(GLOBE_STORE_PATH), exist_ok=True)
    if not os.path.exists(GLOBE_STORE_PATH):
        default_data = {
            "markers": SEED_INTEL_MARKERS,
            "satellites": SEED_SATELLITES,
            "globe_radius_km": 6371.0
        }
        with open(GLOBE_STORE_PATH, "w") as f:
            json.dump(default_data, f, indent=2)
        return default_data

    try:
        with open(GLOBE_STORE_PATH, "r") as f:
            d = json.load(f)
            # Ensure markers list has full seed roster if empty
            if not d.get("markers") or len(d.get("markers", [])) < 3:
                existing_names = [m.get("name") for m in d.get("markers", [])]
                for seed_m in SEED_INTEL_MARKERS:
                    if seed_m.get("name") not in existing_names:
                        d.setdefault("markers", []).append(seed_m)
            if not d.get("satellites"):
                d["satellites"] = SEED_SATELLITES
            return d
    except Exception:
        return {"markers": SEED_INTEL_MARKERS, "satellites": SEED_SATELLITES}

def _save_globe_store(data: dict):
    os.makedirs(os.path.dirname(GLOBE_STORE_PATH), exist_ok=True)
    with open(GLOBE_STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)

def project_spherical_to_cartesian(lat: float, lon: float, radius: float = 6371.0) -> dict:
    """Project spherical lat/lon into 3D Cartesian coordinates (X, Y, Z)."""
    phi = math.radians(lat)
    theta = math.radians(lon)
    x = round(radius * math.cos(phi) * math.cos(theta), 2)
    y = round(radius * math.cos(phi) * math.sin(theta), 2)
    z = round(radius * math.sin(phi), 2)
    return {"x": x, "y": y, "z": z, "radius": radius}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great-Circle geodesic distance in kilometers between two points on Earth."""
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def add_intel_marker(name: str, lat: float, lon: float, marker_type: str = "asset", threat_level: str = "low") -> dict:
    """Register spatial telemetry asset or detected threat vector."""
    store = _ensure_globe_store()
    coords = project_spherical_to_cartesian(lat, lon)
    marker = {
        "id": f"marker-{secrets.token_hex(4)}",
        "name": name,
        "lat": lat,
        "lon": lon,
        "type": marker_type,
        "threat_level": threat_level,
        "cartesian": coords,
        "timestamp": int(time.time())
    }
    store.setdefault("markers", []).insert(0, marker)
    _save_globe_store(store)
    return {"success": True, "marker": marker}

def get_globe_telemetry() -> dict:
    """Telemetry summary for settings poll."""
    store = _ensure_globe_store()
    raw_markers = store.get("markers") or store.get("nodes") or SEED_INTEL_MARKERS
    if len(raw_markers) < 3:
        raw_markers = SEED_INTEL_MARKERS
    sats = store.get("satellites") or SEED_SATELLITES
    
    # Calculate cartesian vectors for each marker
    enriched_markers = []
    for m in raw_markers:
        m_copy = dict(m)
        m_copy["cartesian"] = project_spherical_to_cartesian(m.get("lat", 0.0), m.get("lon", 0.0))
        enriched_markers.append(m_copy)

    return {
        "success": True,
        "assets_count": len(enriched_markers),
        "satellites_count": len(sats),
        "intel_markers": enriched_markers,
        "satellites": sats,
        "globe_radius_km": 6371.0
    }
