#!/usr/bin/env python3
"""Script autonome de vérification des alertes météo — conçu pour être lancé par crontab.

Appelle l'API directement, évalue les seuils, et envoie des notifications macOS
via osascript si des alertes sont détectées.

Crontab recommandé (toutes les 20 min) :
    */20 * * * * /Users/samuelbouhenic/code/AgentWS/weather-mcp/.venv/bin/python \
        /Users/samuelbouhenic/code/AgentWS/weather-mcp/alert_checker.py \
        >> /tmp/meteo-alerts.log 2>&1
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = "https://weatherstation.cielnewton.fr"


def _api_key() -> str:
    """Clé API : variable d'environnement WEATHER_API_KEY, sinon fichier .api_key
    à côté de ce script (gitignoré)."""
    key = os.environ.get("WEATHER_API_KEY", "")
    if not key:
        key_file = Path(__file__).parent / ".api_key"
        if key_file.exists():
            key = key_file.read_text()
    return key.strip()


HEADERS = {"X-API-Key": _api_key()}

SNAPSHOT_FIELDS = [
    "temperature", "tempDS18B20", "humidity", "pressure",
    "rainfall", "avgSpeed", "maxSpeed", "avgDirectionCardinal",
    "batteryVoltage", "iaq",
]

UNITS = {
    "temperature": "°C", "tempDS18B20": "°C", "humidity": "%",
    "pressure": "hPa", "rainfall": "mm", "avgSpeed": "km/h",
    "maxSpeed": "km/h", "batteryVoltage": "V", "iaq": "",
}

ALERT_THRESHOLDS = {
    "temperature":    {"min": -5.0,  "max": 35.0},
    "batteryVoltage": {"min": 3.5,   "max": None},
    "iaq":            {"min": None,  "max": 200.0},
    "humidity":       {"min": None,  "max": 90.0},
}
OFFLINE_MINUTES = 30
RAIN_THRESHOLD = 0.0


async def fetch(field: str) -> tuple[str, list[dict]]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{BASE_URL}/api/data/{field}", params={"duration": "-1h"}, headers=HEADERS)
            r.raise_for_status()
            return field, r.json()
    except Exception:
        return field, []


def last(points: list[dict]) -> dict | None:
    return max(points, key=lambda p: p["_time"]) if points else None


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


async def get_snapshot() -> dict:
    results = await asyncio.gather(*[fetch(f) for f in SNAPSHOT_FIELDS])
    snapshot = {}
    for field, points in results:
        pt = last(points)
        snapshot[field] = {"value": pt["_value"], "time": pt["_time"]} if pt else None
    return snapshot


def evaluate_alerts(snapshot: dict) -> list[str]:
    alerts = []
    now = datetime.now(timezone.utc)

    times = [parse_ts(v["time"]) for v in snapshot.values() if v]
    if not times:
        return ["Station HORS LIGNE — aucune donnée disponible"]
    age = (now - max(times)).total_seconds() / 60
    if age > OFFLINE_MINUTES:
        alerts.append(f"Station HORS LIGNE — dernier relevé il y a {age:.0f} min")

    for field, bounds in ALERT_THRESHOLDS.items():
        data = snapshot.get(field)
        if not data or not isinstance(data.get("value"), (int, float)):
            continue
        v = data["value"]
        unit = UNITS.get(field, "")
        decimals = 2 if field == "batteryVoltage" else 1
        vstr = f"{v:.{decimals}f}"
        if bounds["min"] is not None and v < bounds["min"]:
            alerts.append(f"{field} BAS : {vstr}{unit} (min {bounds['min']}{unit})")
        if bounds["max"] is not None and v > bounds["max"]:
            alerts.append(f"{field} ÉLEVÉ : {vstr}{unit} (max {bounds['max']}{unit})")

    rain = snapshot.get("rainfall")
    if rain and isinstance(rain.get("value"), (int, float)) and rain["value"] > RAIN_THRESHOLD:
        alerts.append(f"Pluie détectée : {rain['value']:.1f} mm")

    return alerts


def notify_macos(title: str, message: str) -> None:
    script = f'display notification "{message}" with title "{title}" sound name "Basso"'
    subprocess.run(["osascript", "-e", script], check=False)


def main() -> None:
    snapshot = asyncio.run(get_snapshot())
    alerts = evaluate_alerts(snapshot)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not alerts:
        print(f"[{ts}] OK — aucune alerte")
        return

    for alert in alerts:
        print(f"[{ts}] ALERTE : {alert}")

    summary = " | ".join(alerts)
    notify_macos("Station Météo Newton", summary[:200])
    sys.exit(1)  # Code de sortie non-zéro pour que cron puisse logguer


if __name__ == "__main__":
    main()
