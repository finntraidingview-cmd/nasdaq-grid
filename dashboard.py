# -*- coding: utf-8 -*-
"""dashboard.py — Uebersicht fuer den Nasdaq-Grid im Browser, laeuft nur auf diesem PC.
Liest die Dateien, die grid.py schreibt (status-*.json, verlauf-*.json, log-*.txt) und zeigt sie
unter http://localhost:8790 an. Sendet keine Order und aendert nichts.  Aufruf: start-dashboard.bat"""
import json, os, time, glob, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HIER = os.path.dirname(os.path.abspath(__file__))
PORT = 8790


def lies(pfad, ersatz):
    # Der Bot ersetzt die Datei gerade? Dann kurz nochmal — nie mit halbem Inhalt antworten.
    for _ in range(3):
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            time.sleep(0.05)
    return ersatz


def log_ende(pfad, zeilen=60):
    try:
        with open(pfad, "rb") as f:
            f.seek(0, 2); groesse = f.tell(); f.seek(max(0, groesse - 20000))
            return f.read().decode("utf-8", "replace").splitlines()[-zeilen:]
    except OSError:
        return []


def seiten_version():
    try:
        with open(os.path.join(HIER, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def selbst_update():
    """Alle 2 Minuten nach einer neuen Version sehen. Die Seite (dashboard.html) wird von der Platte
    gelesen und ist damit sofort neu; hat sich dashboard.py selbst geaendert, beendet sich der
    Server und die .bat-Schleife startet den neuen. Der Browser laedt sich ueber 'version' neu."""
    eigen = os.path.abspath(__file__)
    stand = os.path.getmtime(eigen)
    while True:
        time.sleep(20)
        # Neu starten, sobald dashboard.py auf der Platte neuer ist — egal wer das Update geholt hat
        # (01.10.2026: ein Bot hatte es geholt, die Uebersicht lief mit dem alten Programm weiter).
        try:
            if os.path.getmtime(eigen) != stand:
                print("neue Version von dashboard.py — Neustart", flush=True)
                os._exit(0)
        except OSError:
            pass
        if int(time.time()) % 120 < 20:
            try:
                import importlib, update
                importlib.reload(update)
                update.lauf(leise=True)
            except Exception:
                pass


def daten():
    bots = {}
    for pfad in sorted(glob.glob(os.path.join(HIER, "status-*.json"))):
        stamm = os.path.basename(pfad)[len("status-"):-len(".json")]
        st = lies(pfad, None)
        if not st:
            continue
        st["alter_s"] = round(time.time() - float(st.get("geschrieben", 0)), 1)
        st["verlauf"] = lies(os.path.join(HIER, f"verlauf-{stamm}.json"), [])
        st["log"] = log_ende(os.path.join(HIER, f"log-{stamm}.txt"))
        bots[st.get("bot", stamm)] = st
    return {"jetzt": time.time(), "version": seiten_version(), "bots": bots}


EINST_FELDER = ("start_lot", "schritt_lot", "schritt_prozent", "start", "ende")
STANDARD_TERMINAL = {"long": r"C:\MT5-Grid-Long\terminal64.exe", "short": r"C:\MT5-Grid-Short\terminal64.exe"}


def einstellungen_lesen():
    out = {}
    for r in ("long", "short"):
        c = lies(os.path.join(HIER, f"config-{r}.json"), None)
        if c is None:
            c = lies(os.path.join(HIER, f"config-{r}.vorlage.json"), {})
            c["expected_login"] = 0; c["terminal_path"] = ""
        c.pop("_hinweis", None)
        out[r] = c
    return out


def uhrzeit_ok(t):
    try:
        h, m = str(t).split(":"); return 0 <= int(h) <= 23 and 0 <= int(m) <= 59 and len(str(t)) == 5
    except ValueError:
        return False


def einstellungen_speichern(neu):
    """Prueft und schreibt config-long.json und config-short.json. Liefert (ok, meldung)."""
    alt = einstellungen_lesen()
    g = neu.get("gemeinsam") or {}
    try:
        # Zeiten stellt Finn nicht mehr ein (01.10.2026): fest 00:01 bis 22:00 deutscher Zeit — bleiben wie in der Config.
        gemeinsam = {"start_lot": round(float(g["start_lot"]), 2), "schritt_lot": round(float(g["schritt_lot"]), 2),
                     "schritt_prozent": round(float(g["schritt_prozent"]), 3),
                     "start": str(g.get("start") or alt["long"].get("start") or "01:01"), "ende": str(g.get("ende") or alt["long"].get("ende") or "23:00")}
    except (KeyError, ValueError, TypeError):
        return False, "Start-Lot, Lot je Stufe und Abstand muessen ausgefuellt sein."
    if not (0 <= gemeinsam["start_lot"] <= 10): return False, "Start-Lot zwischen 0 und 10."
    if not (0.01 <= gemeinsam["schritt_lot"] <= 1): return False, "Lot je Stufe zwischen 0,01 und 1."
    if not (0.01 <= gemeinsam["schritt_prozent"] <= 5): return False, "Abstand zwischen 0,01 und 5 %."
    if not (uhrzeit_ok(gemeinsam["start"]) and uhrzeit_ok(gemeinsam["ende"])): return False, "Zeiten als HH:MM angeben."
    if gemeinsam["start"] >= gemeinsam["ende"]: return False, "Start muss vor Ende liegen."
    geschrieben = []
    for r in ("long", "short"):
        e = neu.get(r) or {}
        try:
            login = int(str(e.get("expected_login", "")).strip())
        except ValueError:
            return False, f"Kontonummer {r} nur Ziffern."
        # Terminal fest: C:\MT5-Grid-Long bzw. C:\MT5-Grid-Short (Finn 01.10.2026, kein Eingabefeld mehr).
        pfad = STANDARD_TERMINAL[r]
        if login <= 0: return False, f"Kontonummer {r} fehlt."
        if not os.path.isfile(pfad): return False, f"Terminal {r} nicht gefunden: {pfad}"
        c = dict(alt[r]); c.update(gemeinsam)
        # scharf/laeuft stellt nur der Start-/Stopp-Knopf — Speichern laesst sie, wie sie sind.
        c.update({"expected_login": login, "terminal_path": pfad, "richtung": r})
        try:
            import einrichten
            einrichten.archiviere_bei_kontowechsel(r, login)
        except Exception:
            pass
        ziel = os.path.join(HIER, f"config-{r}.json")
        with open(ziel + ".neu", "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2, ensure_ascii=False)
        os.replace(ziel + ".neu", ziel)
        geschrieben.append(r)
    return True, "Gespeichert — die Bots uebernehmen die Werte in wenigen Sekunden."


def schalte(scharf=None, laeuft=None):
    """Start/Stopp fuer beide Bots: setzt scharf/laeuft in beiden Configs (die Bots starten dann neu)."""
    for r in ("long", "short"):
        pfad = os.path.join(HIER, f"config-{r}.json")
        c = lies(pfad, None)
        if not c or not int(c.get("expected_login") or 0):
            return False, "Erst Kontonummern speichern."
        if scharf is not None:
            c["scharf"] = scharf
        if laeuft is not None:
            c["laeuft"] = laeuft
        with open(pfad + ".neu", "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2, ensure_ascii=False)
        os.replace(pfad + ".neu", pfad)
    return True, ("Gestartet — beide Bots eroeffnen in wenigen Sekunden." if laeuft else "Gestoppt — alle Positionen werden geschlossen.")


def statistik_zuruecksetzen():
    """Tagesbuch und Log nach archiv/zurueckgesetzt-<Zeit>/ legen und die Bots neu starten lassen
    (dadurch beginnt auch die Tageskurve neu). Anker und Stufe des laufenden Tages bleiben."""
    ziel = os.path.join(HIER, "archiv", time.strftime("zurueckgesetzt-%Y%m%d-%H%M%S"))
    os.makedirs(ziel, exist_ok=True)
    for muster in ("verlauf-*.json", "log-*.txt"):
        for p in glob.glob(os.path.join(HIER, muster)):
            try:
                os.replace(p, os.path.join(ziel, os.path.basename(p)))
            except OSError:
                pass
    for r in ("long", "short"):
        p = os.path.join(HIER, f"config-{r}.json")
        if os.path.isfile(p):
            os.utime(p, None)                  # geaenderte Config = Bot startet neu
    return True, "Statistik zurueckgesetzt — alte Werte liegen in archiv."


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _antwort(self, code, daten):
        body = json.dumps(daten).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # Schutz gegen fremde Webseiten im selben Browser: nur eigener Host, nur mit eigenem Kopf
        # (den darf eine fremde Seite ohne Freigabe nicht setzen), nur JSON.
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("localhost", "127.0.0.1") or self.headers.get("X-Nasdaq-Grid") != "1" \
                or not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._antwort(403, {"ok": False, "meldung": "abgelehnt"})
        try:
            laenge = min(int(self.headers.get("Content-Length") or 0), 20000)
            neu = json.loads(self.rfile.read(laenge).decode("utf-8") or "{}")
            if self.path == "/api/einstellungen":
                ok, meldung = einstellungen_speichern(neu)
            elif self.path == "/api/start":
                ok, meldung = schalte(scharf=True, laeuft=True)
            elif self.path == "/api/stop":
                ok, meldung = schalte(laeuft=False)
            elif self.path == "/api/reset":
                ok, meldung = statistik_zuruecksetzen()
            else:
                return self._antwort(404, {"ok": False})
        except Exception as e:
            ok, meldung = False, f"Fehler: {type(e).__name__}"
        return self._antwort(200 if ok else 400, {"ok": ok, "meldung": meldung})

    def do_GET(self):
        if self.path.startswith("/api/einstellungen"):
            return self._antwort(200, einstellungen_lesen())
        if self.path.startswith("/api/status"):
            body = json.dumps(daten()).encode("utf-8"); typ = "application/json; charset=utf-8"
        elif self.path in ("/", "/index.html"):
            with open(os.path.join(HIER, "dashboard.html"), "rb") as f:
                body = f.read()
            typ = "text/html; charset=utf-8"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", typ); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"Nasdaq-Grid Uebersicht: http://localhost:{PORT}  (Fenster zu = Uebersicht aus, die Bots laufen weiter)")
    threading.Thread(target=selbst_update, daemon=True).start()
    # Nur auf diesem PC erreichbar (127.0.0.1) — im Status stehen Kontonummern und Guthaben.
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
