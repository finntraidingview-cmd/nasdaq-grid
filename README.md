# Nasdaq-Grid — Long-Bot und Short-Bot

Eigenes Projekt, hat mit Prophos nichts zu tun. Zwei MT5-Konten bei Fusion Markets,
je Konto ein Prozess mit denselben Einstellungen.

- **Long-Bot:** startet zum Tagesbeginn mit 1,0 Lot long. Je 0,1 %, die NAS100 steigt,
  verkauft er 0,01 Lot aus der Position; je 0,1 %, die er fällt, kauft er 0,01 Lot nach.
- **Short-Bot:** startet mit 1,0 Lot short. Je 0,1 % nach oben verkauft er 0,01 Lot dazu,
  je 0,1 % nach unten kauft er 0,01 Lot zurück.
- **Tagesrhythmus:** Start 01:01 Serverzeit (00:01 deutscher Zeit), um 23:00 Serverzeit
  (22:00 deutscher Zeit) wird alles geschlossen.

## Einrichten auf dem PC (einmal)

1. In PowerShell ausführen (legt `C:\Nasdaq-Grid` an, lädt alles, installiert bei Bedarf `MetaTrader5`):
   `irm https://raw.githubusercontent.com/finntraidingview-cmd/nasdaq-grid/main/installieren.ps1 | iex`
2. Zwei MT5-Terminals in zwei Ordnern, in jedem ist eines der Konten eingeloggt,
   „Algo-Trading" ist an.
3. `einrichten.bat` starten: fragt je Bot nach Terminal-Ordner und Kontonummer, schreibt
   `config-long.json` und `config-short.json` und prüft die Verbindung (ohne zu handeln).
4. `start-long.bat` und `start-short.bat` starten. Solange `"scharf": false` steht,
   schreibt der Bot nur ins Log, was er tun würde.
5. Wenn der Trockenlauf stimmt: in beiden Configs `"scharf": true`, Fenster schließen,
   neu starten.

Updates kommen von selbst: Der Bot prüft alle 5 Minuten die `VERSION` im Repo und startet bei einer neuen neu.

Fenster zu = Bot aus. Offene Positionen bleiben dann stehen, bis der Bot wieder läuft
oder sie von Hand geschlossen werden.

## Dateien

| Datei | Zweck |
|---|---|
| `grid.py` | der Bot (ein Prozess je Konto) |
| `selftest.py` | prüft die Logik ohne MT5: `python selftest.py` |
| `einrichten.bat`, `einrichten.py` | Einrichtungs-Hilfe und Verbindungs-Prüfung |
| `config-*.vorlage.json` | Ausgangswerte der Einstellungen |
| `start-long.bat`, `start-short.bat` | Start mit Selbst-Update und automatischem Neustart |
| `installieren.ps1` | Ersteinrichtung auf einem PC |
| `start-dashboard.bat`, `dashboard.py`, `dashboard.html` | Übersicht im Browser unter http://localhost:8790 (nur auf diesem PC, sendet nichts) |
| `VERSION` | jede Änderung am Bot erhöht sie — das löst das Update auf den PCs aus |
| `log-*.txt`, `zustand-*.json`, `status-*.json`, `verlauf-*.json` | entstehen beim Laufen |
