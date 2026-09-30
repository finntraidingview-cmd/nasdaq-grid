# -*- coding: utf-8 -*-
"""dashboard.py — Uebersicht fuer den Nasdaq-Grid im Browser, laeuft nur auf diesem PC.
Liest die Dateien, die grid.py schreibt (status-*.json, verlauf-*.json, log-*.txt) und zeigt sie
unter http://localhost:8790 an. Sendet keine Order und aendert nichts.  Aufruf: start-dashboard.bat"""
import json, os, time, glob, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HIER = os.path.dirname(os.path.abspath(__file__))
PORT = 8790


def lies(pfad, ersatz):
    try:
        with open(pfad, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
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
    while True:
        time.sleep(120)
        try:
            import importlib, update
            importlib.reload(update)
            if "dashboard.py" in update.lauf(leise=True):
                print("neue Version von dashboard.py — Neustart", flush=True)
                os._exit(0)
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


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
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
