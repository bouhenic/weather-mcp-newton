# Serveur MCP — Station Météo Newton

Serveur [MCP](https://modelcontextprotocol.io) local pour interroger la station météo LoRaWAN du Lycée Newton (Clichy) depuis **Claude Desktop** en langage naturel.

```
Capteurs → LoRaWAN → TTN → InfluxDB → API REST → Serveur MCP → Claude Desktop
```

## Outils exposés

| Outil | Description |
|---|---|
| `get_current_snapshot` | Dernier relevé de tous les capteurs (température, humidité, pression, vent, pluie…) |
| `get_field_history(field, duration)` | Historique d'un capteur avec min / max / moyenne (-1h à -30d) — accepte aussi les champs radio (`rssi`, `snr`, `spreadingFactor`…) |
| `get_radio_status` | État du lien radio LoRaWAN de la station : RSSI, SNR, SF, canal, passerelles, airtime |
| `get_gateway_traffic(duration)` | Activité de la passerelle : trafic tous réseaux (TTN vs autres), devices distincts, bruit CRC, duty cycle EU868 |
| `check_alerts` | Vérifie les seuils (température, batterie, IAQ, humidité, hors-ligne, pluie) et retourne les alertes actives |

## Installation

```bash
git clone https://github.com/samuelbouhenic/weather-mcp-newton
cd weather-mcp-newton
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Intégration dans Claude Desktop

Ajoute dans `~/Library/Application Support/Claude/claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "station-meteo": {
      "command": "/chemin/vers/weather-mcp-newton/.venv/bin/python",
      "args": ["/chemin/vers/weather-mcp-newton/server.py"]
    }
  }
}
```

Redémarre Claude Desktop — une icône marteau apparaît dans les nouvelles conversations.

> Le guide complet est disponible dans [`guide-integration-mcp.pdf`](./guide-integration-mcp.pdf).

## Stack

- [`fastmcp`](https://github.com/jlowin/fastmcp) — framework MCP Python
- [`httpx`](https://www.python-httpx.org/) — requêtes HTTP async
- API station : `https://weatherstation.cielnewton.fr/api/data/{field}?duration=-1h`
