# AURORA AI TRADER — Version 0.3

Deutschsprachige Web-App für öffentliche Kraken-Marktdaten und ausschließlich simuliertes Paper-Trading. Es gibt keine Kraken-Kontoanbindung, keine privaten API-Schlüssel und keinen Code für Echtgeldorders.

## Sicherheit

Alle Dashboard-, statischen und API-Routen sind mit HTTP Basic Auth geschützt. Nur `/healthz` ist für Render-Gesundheitschecks öffentlich. Schreibende Browser-Anfragen werden zusätzlich auf denselben Origin beschränkt. Fehlen Zugangsdaten, antwortet die App mit HTTP 503; der automatische Scanner startet dann ebenfalls nicht.

In Render müssen vor dem Resume/Deploy diese geheimen Environment Variables gesetzt sein:
- `AURORA_USERNAME`: selbst gewählter Benutzername (ohne Doppelpunkt)
- `AURORA_PASSWORD`: langes, einzigartiges Passwort (mindestens 20 Zeichen empfohlen)

Zugangsdaten niemals in GitHub, `render.yaml`, Screenshots oder Quellcode eintragen. Render stellt HTTPS für die öffentliche Service-URL bereit. Der Browser fragt beim ersten Aufruf nach Benutzername und Passwort.

## Kostenloser Render-Testbetrieb

`render.yaml` verwendet `plan: free` und `AURORA_DB=/tmp/aurora.db`. Es wird kein kostenpflichtiger Datenträger angelegt. Das Dateisystem des kostenlosen Dienstes ist flüchtig; virtuelle Kontostände, Trades und Signale können bei Neustarts/Neu-Deployments verloren gehen. Kostenlose Web Services schlafen nach Inaktivität ein und sind nicht für zuverlässigen 24/7-Betrieb geeignet.

## Funktionen und Grenzen

- Öffentliche Kraken-REST-Daten: Märkte, Ticker und OHLC-Kerzen
- EMA 12/26, RSI 14 und 5-Kerzen-Momentum als heuristischer Signal-Score; keine trainierte KI und keine Gewinnwahrscheinlichkeit
- Virtuelle Kauf-/Verkaufsorders, Positionen und Historie; angenommene Gebühren 0,4 % und Slippage 0,1 %
- Automatischer Paper-Scanner: bis zu 10 EUR-Märkte, standardmäßig 60-Sekunden-Zyklus, maximal 200 EUR je Einstieg und 15-Minuten-Cooldown je Markt
- Keine echten Orders; der Scanner führt ausschließlich interne Paper-Orders aus
- Auf Render Free läuft der Scanner nur solange der Dienst wach ist; während des Schlafens findet kein Scan statt
- SQLite auf `/tmp` ist nicht dauerhaft; Datenverlust bei Neustart möglich
- Kein Backtesting, keine validierte Strategie, keine Renditegarantie und keine Anlageberatung

## Starten

```bash
pip install -r requirements.txt
export AURORA_USERNAME='dein-benutzername'
export AURORA_PASSWORD='dein-langes-passwort'
uvicorn app:app --host 127.0.0.1 --port 8000
```

Danach `http://127.0.0.1:8000` öffnen und im Browser anmelden.
