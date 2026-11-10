# AURORA AI TRADER 0.2 — Paper Trading only

## Funktionen
- Öffentliche Kraken-Spot-Marktdaten (kein Kraken-Konto/API-Key nötig)
- EUR-Spotmärkte, bevorzugt BTC, ETH, SOL, XRP, ADA und LINK
- Technische Heuristik: EMA 12/26, RSI 14 und 5-Kerzen-Momentum
- Automatischer Paper-Scanner mit bis zu 10 EUR-Märkten
- Virtuelle Orders, SQLite-Portfolio und Signalhistorie
- Startkapital 10.000 EUR; maximal 200 EUR je automatischem Einstieg (konfigurierbar)
- Automatik kann im Dashboard deaktiviert werden; separate Paper-Pause

## Lokal starten
Python 3.11+ empfohlen.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```
Öffne http://127.0.0.1:8000

## Render-Konfiguration
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Für dauerhafte SQLite-Daten: Render Persistent Disk mounten und `AURORA_DB=/var/data/aurora.db` setzen; alternativ PostgreSQL implementieren.
- Setze `AUTO_PAPER_DEFAULT=true`, `AUTO_INTERVAL_SECONDS=60`, `MAX_TRADE_EUR=200`, `MAX_OPEN_MARKETS=10`.
- Ein kostenloser/ephemerer Web-Service ist nicht für zuverlässiges 24/7-Trading geeignet.

## Wichtige Grenzen / Sicherheit
**Ausschließlich Paper-Trading.** Es gibt keine Kraken-Privat-API, keine Echtgeldorders und keine Gewinnzusage. Die „KI“ ist aktuell eine transparente technische Regelheuristik, kein trainiertes ML-Modell.

Vor öffentlicher Bereitstellung sind Authentifizierung/Autorisierung, CSRF-Schutz, Rate-Limits, sichere Session-Verwaltung, Datenbankmigrationen, Monitoring und Tests zu ergänzen. Die API ist in diesem Entwicklungsstand nicht für ungeschützte öffentliche Bereitstellung freigegeben. Verwende keine API-Schlüssel im Repository.

Die Strategie ist experimentell. RSI/EMA-Signale können Verluste erzeugen; Backtests und Paper-Ergebnisse sind keine Garantie für zukünftige Resultate.
