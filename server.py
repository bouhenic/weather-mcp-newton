"""Serveur MCP — Station météo LoRaWAN du Lycée Newton (Clichy).

Expose deux outils à tout client MCP (Claude Desktop, Claude Code…) :
- get_current_snapshot : dernier relevé de tous les capteurs
- get_field_history    : historique d'un capteur avec min/max/moyenne
"""

from typing import Literal
import asyncio
import httpx
from fastmcp import FastMCP

BASE_URL = "https://weatherstation.cielnewton.fr"

NUMERIC_FIELDS = [
    "temperature",        # °C  (BME680)
    "tempDS18B20",        # °C  (DS18B20)
    "humidity",           # %
    "pressure",           # hPa
    "rainfall",           # mm
    "avgSpeed",           # km/h
    "maxSpeed",           # km/h
    "avgDirection",       # °
    "maxSpeedDirection",  # °
    "batteryVoltage",     # V
    "gas",                # kΩ
    "iaq",
]
TEXT_FIELDS = ["avgDirectionCardinal", "maxSpeedDirectionCardinal"]
ALL_FIELDS = NUMERIC_FIELDS + TEXT_FIELDS

SNAPSHOT_FIELDS = [
    "temperature", "tempDS18B20", "humidity", "pressure",
    "rainfall", "avgSpeed", "maxSpeed", "avgDirectionCardinal",
    "batteryVoltage", "iaq",
]

UNITS = {
    "temperature": "°C", "tempDS18B20": "°C", "humidity": "%",
    "pressure": "hPa", "rainfall": "mm", "avgSpeed": "km/h",
    "maxSpeed": "km/h", "avgDirection": "°", "maxSpeedDirection": "°",
    "batteryVoltage": "V", "gas": "kΩ", "iaq": "",
}

FieldName = Literal[
    "temperature", "tempDS18B20", "humidity", "pressure", "rainfall",
    "avgSpeed", "maxSpeed", "avgDirection", "maxSpeedDirection",
    "batteryVoltage", "gas", "iaq",
    "avgDirectionCardinal", "maxSpeedDirectionCardinal",
]

mcp = FastMCP("Station Météo Newton")


async def _fetch(field: str, duration: str) -> tuple[str, list[dict]]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{BASE_URL}/api/data/{field}", params={"duration": duration})
            r.raise_for_status()
            return field, r.json()
    except Exception:
        return field, []


def _last(points: list[dict]) -> dict | None:
    return max(points, key=lambda p: p["_time"]) if points else None


@mcp.tool()
def get_current_snapshot() -> str:
    """Retourne le dernier relevé de tous les capteurs de la station météo LoRaWAN :
    température (BME680 + DS18B20), humidité, pression, précipitations,
    vitesse/direction du vent, batterie, IAQ. Utiliser pour toute question sur les
    conditions météo actuelles."""

    async def _all():
        return await asyncio.gather(*[_fetch(f, "-1h") for f in SNAPSHOT_FIELDS])

    results = asyncio.run(_all())
    snapshot = {}
    for field, points in results:
        latest = _last(points)
        if latest:
            snapshot[field] = {"value": latest["_value"], "unit": UNITS.get(field, ""), "time": latest["_time"]}
        else:
            snapshot[field] = None

    if not any(snapshot.values()):
        return "Aucune donnée récente disponible (station hors ligne ?)."

    latest_ts = max(v["time"] for v in snapshot.values() if v)
    lines = [f"Dernier relevé : {latest_ts}"]
    for field, data in snapshot.items():
        if data:
            lines.append(f"  {field}: {data['value']} {data['unit']}")
        else:
            lines.append(f"  {field}: N/A")
    return "\n".join(lines)


@mcp.tool()
def get_field_history(field: FieldName, duration: str) -> str:
    """Retourne l'historique d'un capteur spécifique sur une durée donnée.
    Fournit min, max, moyenne et la série temporelle complète.
    Durées acceptées : -1h, -6h, -24h, -7d, -30d (format Flux InfluxDB)."""

    async def _get():
        return await _fetch(field, duration)

    _, points = asyncio.run(_get())

    if not points:
        return f"Aucune donnée pour '{field}' sur {duration}."

    unit = UNITS.get(field, "")
    values = [p["_value"] for p in points if isinstance(p.get("_value"), (int, float))]
    lines = [f"Champ : {field} | Durée : {duration} | {len(points)} mesure(s)"]
    if values:
        lines += [
            f"  Min     : {min(values):.1f} {unit}",
            f"  Max     : {max(values):.1f} {unit}",
            f"  Moyenne : {sum(values)/len(values):.1f} {unit}",
            f"  Dernier : {values[-1]:.1f} {unit} à {points[-1]['_time']}",
            "\nSérie complète :",
        ]
        for p in points:
            lines.append(f"  {p.get('_time')} → {p.get('_value')} {unit}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
