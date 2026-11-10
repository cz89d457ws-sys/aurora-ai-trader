# AURORA AI TRADER — MVP 0.1

Deutschsprachige, lokal ausführbare Web-App für **öffentliche Kraken-Marktdaten**, technische Signale und **ausschließlich simuliertes Paper-Trading**. Keine API-Schlüssel nötig; es existiert **kein Code für Echtgeldorders**.

## Starten

Python 3.12+ installieren. Im entpackten Projektordner:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Danach im Browser `http://127.0.0.1:8000` öffnen.

## Was funktioniert?
- Öffentliche Kraken-REST-Daten: handelbare Märkte, Ticker und OHLC-Kerzen
- EUR-Spot-Märkte, Suche über die Auswahlliste
- EMA 12/26, RSI 14, 5-Kerzen-Momentum, erklärbarer Signal-Score
- Virtuelle Kauf- und Verkaufsorders, virtuelle Positionen und Historie
- SQLite-Speicherung im lokalen Projektordner (`aurora.db`)
- Pause/Fortsetzen von Paper-Trading
- Mobilfreundliche deutschsprachige Oberfläche

## Grenzen
- **Kein trainiertes KI-Modell**: Der Signal-Score ist eine einfache Indikatorheuristik und nicht als Gewinnwahrscheinlichkeit zu verstehen.
- **Keine automatische Orderstrategie** und keine Echtgeldanbindung.
- **Keine Benutzeranmeldung**: Nur lokal an `127.0.0.1` betreiben, nicht ungeschützt ins Internet stellen.
- Simulierte Orderausführung zu öffentlichem Bid/Ask plus pauschal 0,1 % Slippage und 0,4 % Gebühren. Keine echte Orderbuchausführung, Teilausführung oder markt-/volumenabhängige Gebühr.
- Cash und Positionskosten werden angezeigt, noch keine vollständige mark-to-market Bewertung oder PnL.
- Kein Backtesting, keine Modellvalidierung, keine produktionsreifen Risikolimits.
- Kraken API/Marktverfügbarkeit und Netzwerkverbindung können sich ändern.

## Roadmap
1. Automatische Tests, Fehlerfälle, lokale Order- und Portfolioabgleiche
2. Preisverlauf und Portfolio-Mark-to-Market, PnL und Gebührenmodell
3. Historische Datenpipeline, Backtesting, Walk-forward-Tests
4. Kalibrierte ML-Modelle gegen einfache Baselines, Driftüberwachung
5. WebSocket-Livefeed, robuste Wiederverbindung, Rate-Limits
6. Authentifizierung, HTTPS, verschlüsselte Secrets, Audit-Logs
7. Erst nach gesonderter Sicherheitsprüfung und ausdrücklicher Freigabe: Echtgeldmodul

Keine Anlageberatung und keine Garantie für Profit.
