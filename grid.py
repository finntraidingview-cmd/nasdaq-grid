# -*- coding: utf-8 -*-
"""grid.py — Nasdaq-Grid auf EINEM MT5-Konto: entweder Long-Bot oder Short-Bot.

Finns Setup vom 30.09.2026: Zwei Konten, zwei Prozesse, gleiche Einstellungen.
  Long-Bot : startet zum Tagesbeginn mit start_lot LONG. Je schritt_prozent, die der
             Markt steigt, wird schritt_lot verkauft (aus der Start-Position heraus);
             je schritt_prozent, die er faellt, wird schritt_lot nachgekauft.
  Short-Bot: startet mit start_lot SHORT. Je Schritt nach oben wird schritt_lot
             zusaetzlich verkauft, je Schritt nach unten schritt_lot zurueckgekauft.
Zur Endzeit wird alles geschlossen, am naechsten Tag beginnt es am neuen Kurs.

Der Bot rechnet nur EINE Zahl aus — das Soll-Volumen zur zuletzt beruehrten Stufe —
und gleicht das Konto darauf ab. Dadurch holt er eine abgelehnte Order im naechsten
Durchlauf von selbst nach, und ein Neustart mitten am Tag macht nichts kaputt.

Zeiten sind MT5-SERVERZEIT (Fusion: New York + 7 h; 01:00 Server = 00:00 deutscher
Zeit = Marktstart, 23:00 Server = 22:00 deutscher Zeit). Bewusst nicht die PC-Uhr:
die Serverzeit steht im Tick und ist auf jedem PC gleich.

Wie der Copier: KEIN Login, kein Passwort. initialize() haengt sich an das Terminal,
das schon eingeloggt ist; stimmt die Kontonummer nicht mit der Config, bricht er ab.
Solange "scharf" in der Config false ist, wird nur geloggt, was er tun wuerde.

Aufruf:  python grid.py config-long.json
"""
import json, os, sys, time, datetime as dt
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
MAGIC = 790300          # eigener Block — Copier 770000–779999, Solo-Hedge 790001
# Selbst-Update: steht im Repo eine andere VERSION als hier, beendet sich der Bot und die
# .bat-Schleife laedt den neuen Stand und startet ihn wieder. Mitten am Tag unkritisch:
# Anker und Stufe stehen in zustand-*.json, das Konto wird danach nur wieder abgeglichen.
REPO_RAW = "https://raw.githubusercontent.com/finntraidingview-cmd/nasdaq-grid/main/"
UPDATE_TAKT_S = 300


def lokale_version():
    try:
        with open(os.path.join(HIER, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def repo_version():
    """VERSION aus dem Repo; "" bei jedem Fehler (kein Netz, Repo fehlt) — dann laeuft er einfach weiter."""
    try:
        with urllib.request.urlopen(REPO_RAW + "VERSION", timeout=10) as r:
            v = r.read(64).decode("utf-8", "ignore").strip()
        return v if 0 < len(v) <= 40 and "<" not in v else ""
    except Exception:
        return ""

STANDARD = {
    "terminal_path": "",          # z. B. C:\\MT5-Grid-Long\\terminal64.exe
    "portable": False,
    "expected_login": 0,          # Kontonummer aus der Titelzeile des Terminals
    "symbol": "NAS100",
    "richtung": "long",           # "long" oder "short"
    "start_lot": 1.0,
    "schritt_lot": 0.01,
    "schritt_prozent": 0.1,
    "start": "01:01",             # Serverzeit (= 00:01 deutscher Zeit)
    "ende": "23:00",              # Serverzeit (= 22:00 deutscher Zeit), alles schliessen
    "max_lot": 2.0,               # Deckel fuers Soll-Volumen
    "deviation_points": 50,
    "poll_interval": 0.5,
    "scharf": False,              # erst true = es werden wirklich Orders gesendet
    "laeuft": True,               # false = gestoppt (Knopf in der Uebersicht): alles schliessen, nichts Neues
    "zaehl_ab": 0.0,              # Beginn des laufenden Laufs (Unix-Zeit), gesetzt von "Statistik zuruecksetzen"
}


# ---------------------------------------------------------------- reine Logik
def minuten(hhmm):
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


def stufe_nachfuehren(anker, schritt_prozent, cur, mitte):
    """cur = zuletzt beruehrte Stufe (0 = Anker). Eine neue Stufe zaehlt erst, wenn der
    Kurs sie wirklich erreicht — dazwischen bleibt cur stehen (kein Flattern am Level)."""
    s = anker * schritt_prozent / 100.0
    if s <= 0:
        return cur
    wache = 0
    while anker + (cur + 1) * s <= mitte and wache < 2000:
        cur += 1; wache += 1
    while anker + (cur - 1) * s >= mitte and wache < 2000:
        cur -= 1; wache += 1
    return cur


def soll_volumen(richtung, start_lot, schritt_lot, cur, max_lot, vol_step=0.01):
    """Betrag des Soll-Volumens in der Richtung des Bots (nie negativ)."""
    if richtung == "long":
        v = start_lot - schritt_lot * cur      # steigt der Markt, wird verkauft
    else:
        v = start_lot + schritt_lot * cur      # steigt der Markt, wird mehr geshortet
    v = max(0.0, min(float(max_lot), v))
    return runde(v, vol_step)


def runde(v, vol_step):
    n = round(v / vol_step)
    return round(n * vol_step, 8)


def naechster_zustand(z, heute, minute, mitte, cfg):
    """Fuehrt Tag, Anker und Stufe nach. z = {"tag","anker","cur","fertig"}.
    Liefert (z, aktiv, ereignis) — ereignis ist ein Logtext oder None."""
    start, ende = minuten(cfg["start"]), minuten(cfg["ende"])
    ereignis = None
    if z.get("tag") and not z.get("fertig") and (minute >= ende or z["tag"] != heute):
        z["fertig"] = True
        ereignis = "Tagesende — alles schliessen"
    if z.get("tag") != heute and start <= minute < ende:
        # hoch/runter = beruehrte Stufen je Richtung; jede Stufe hoch UND wieder runter ist eine
        # abgeschlossene Grid-Runde (schritt_lot einmal verkauft und eine Stufe tiefer zurueckgekauft).
        z = {"tag": heute, "anker": mitte, "cur": 0, "fertig": False, "hoch": 0, "runter": 0, "min": 0, "max": 0}
        ereignis = f"neuer Tag, Anker {mitte:.2f}, Schritt {mitte * cfg['schritt_prozent'] / 100.0:.2f} Punkte"
    aktiv = z.get("tag") == heute and not z.get("fertig")
    if aktiv:
        neu = stufe_nachfuehren(z["anker"], cfg["schritt_prozent"], z["cur"], mitte)
        if neu != z["cur"]:
            ereignis = f"Stufe {z['cur']:+d} → {neu:+d} bei {mitte:.2f}"
            if neu > z["cur"]:
                z["hoch"] = z.get("hoch", 0) + (neu - z["cur"])
            else:
                z["runter"] = z.get("runter", 0) + (z["cur"] - neu)
            z["cur"] = neu
            z["min"] = min(z.get("min", 0), neu); z["max"] = max(z.get("max", 0), neu)
    return z, aktiv, ereignis


def abgleich_plan(positionen, soll, vol_step, vol_max=1e9):
    """positionen = [(ticket, volumen)] der eigenen Positionen (alle in Bot-Richtung).
    Liefert Auftraege: ("auf", volumen) oder ("zu", ticket, volumen). Beim Abbauen zuerst
    die kleinen Positionen — die Start-Position bleibt so lange wie moeglich ganz."""
    ist = runde(sum(v for _, v in positionen), vol_step)
    diff = runde(soll - ist, vol_step)
    plan = []
    if diff >= vol_step - 1e-9:
        rest = diff
        while rest >= vol_step - 1e-9:
            v = min(rest, vol_max)
            plan.append(("auf", runde(v, vol_step)))
            rest = runde(rest - v, vol_step)
    elif diff <= -(vol_step - 1e-9):
        rest = -diff
        for ticket, v in sorted(positionen, key=lambda p: (p[1], p[0])):
            if rest < vol_step - 1e-9:
                break
            w = min(v, rest)
            plan.append(("zu", ticket, runde(w, vol_step)))
            rest = runde(rest - w, vol_step)
    return plan


# ---------------------------------------------------------------- Laufzeit
def log(text, pfad=None):
    zeile = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {text}"
    print(zeile, flush=True)
    if pfad:
        try:
            with open(pfad, "a", encoding="utf-8") as f:
                f.write(zeile + "\n")
        except OSError:
            pass


def lies_json(pfad):
    try:
        with open(pfad, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def problem_melden(stamm, cfg, text):
    """Bot kann nicht laufen: statt eines veralteten Stands zeigt die Uebersicht diesen Grund an."""
    pfad = os.path.join(HIER, f"status-{stamm}.json")
    try:
        with open(pfad + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"bot": cfg["richtung"], "problem": text, "erwartet": cfg.get("expected_login"), "geschrieben": time.time()}, f)
        os.replace(pfad + ".tmp", pfad)
    except OSError:
        pass


def lade_config(pfad):
    with open(pfad, "r", encoding="utf-8") as f:
        roh = json.load(f)
    cfg = dict(STANDARD)
    cfg.update({k: v for k, v in roh.items() if not k.startswith("_")})
    cfg["richtung"] = str(cfg["richtung"]).lower()
    if cfg["richtung"] not in ("long", "short"):
        raise ValueError('richtung muss "long" oder "short" sein')
    if not (cfg["schritt_prozent"] > 0 and cfg["schritt_lot"] > 0 and cfg["start_lot"] >= 0):
        raise ValueError("schritt_prozent, schritt_lot > 0 und start_lot >= 0 erforderlich")
    if minuten(cfg["start"]) >= minuten(cfg["ende"]):
        raise ValueError("start muss vor ende liegen (gleicher Servertag)")
    return cfg


def main():
    if len(sys.argv) < 2:
        print("Aufruf: python grid.py config-long.json"); sys.exit(2)
    cfg_pfad = os.path.abspath(sys.argv[1])
    cfg = lade_config(cfg_pfad)
    stamm = os.path.splitext(os.path.basename(cfg_pfad))[0]
    log_pfad = os.path.join(HIER, f"log-{stamm}.txt")
    zustand_pfad = os.path.join(HIER, f"zustand-{stamm}.json")
    L = lambda t: log(f"[{cfg['richtung']}] {t}", log_pfad)

    import MetaTrader5 as mt5
    init_kw = {}
    if cfg["terminal_path"]:
        init_kw["path"] = cfg["terminal_path"]
    if cfg.get("portable"):
        init_kw["portable"] = True
    if not mt5.initialize(**init_kw):
        L(f"⛔ initialize() fehlgeschlagen: {mt5.last_error()} — laeuft das Terminal?")
        problem_melden(stamm, cfg, f"Keine Verbindung zum Terminal {cfg['terminal_path']} ({mt5.last_error()}).")
        sys.exit(1)
    konto = mt5.account_info()
    if konto is None or int(konto.login) != int(cfg["expected_login"]):
        L(f"⛔ falsches Konto im Terminal ({getattr(konto, 'login', None)}) — erwartet {cfg['expected_login']}. ABBRUCH, keine Order.")
        problem_melden(stamm, cfg, f"Im Terminal ist Konto {getattr(konto, 'login', '–')} eingeloggt, eingestellt ist {cfg['expected_login']}. "
                                   f"Kontonummer in den Einstellungen korrigieren oder im Terminal das richtige Konto einloggen.")
        mt5.shutdown(); sys.exit(1)
    sym = cfg["symbol"]
    mt5.symbol_select(sym, True)
    si = mt5.symbol_info(sym)
    if si is None:
        L(f"⛔ Symbol {sym} nicht gefunden"); mt5.shutdown(); sys.exit(1)
    vol_step = float(si.volume_step or 0.01); vol_min = float(si.volume_min or 0.01); vol_max = float(si.volume_max or 1e9)
    if cfg["schritt_lot"] < vol_min - 1e-9:
        L(f"⛔ schritt_lot {cfg['schritt_lot']} unter dem Mindest-Lot {vol_min} von {sym}"); mt5.shutdown(); sys.exit(1)
    fm = int(getattr(si, "filling_mode", 0) or 0)
    filling = mt5.ORDER_FILLING_FOK if fm & 1 else (mt5.ORDER_FILLING_IOC if fm & 2 else mt5.ORDER_FILLING_RETURN)
    kauf_richtung = cfg["richtung"] == "long"
    # Kontowaehrung je Punkt je 1,0 Lot (NAS100 auf EUR-Konto ≈ 0,85)
    _tv, _ts = float(getattr(si, "trade_tick_value", 0.0) or 0.0), float(getattr(si, "trade_tick_size", 0.0) or 0.0)
    punktwert = _tv / _ts if _tv > 0 and _ts > 0 else float(si.trade_contract_size or 1.0)
    L(f"verbunden mit Konto {konto.login}, {sym}, Start {cfg['start_lot']} Lot, Schritt {cfg['schritt_lot']} Lot je {cfg['schritt_prozent']} %, "
      f"{'SCHARF' if cfg['scharf'] else 'TROCKENLAUF (scharf=false, es wird nichts gesendet)'}"
      f"{'' if cfg.get('laeuft', True) else ' — GESTOPPT (schliesst alles, eroeffnet nichts)'}")

    try:
        with open(zustand_pfad, "r", encoding="utf-8") as f:
            z = json.load(f)
    except (OSError, ValueError):
        z = {}

    def eigene():
        ps = mt5.positions_get(symbol=sym) or []
        return [p for p in ps if int(p.magic) == MAGIC]

    def senden(req, was):
        r = mt5.order_send(req)
        if r is None or r.retcode != mt5.TRADE_RETCODE_DONE:
            L(f"❌ {was} abgelehnt: {getattr(r, 'retcode', None)} {getattr(r, 'comment', '')} {mt5.last_error() if r is None else ''}")
            return False
        L(f"✅ {was} @ {getattr(r, 'price', 0):.2f}")
        return True

    status_pfad = os.path.join(HIER, f"status-{stamm}.json")
    verlauf_pfad = os.path.join(HIER, f"verlauf-{stamm}.json")
    kurve = {"tag": None, "punkte": []}       # Tagesergebnis je Minute fuer die Uebersicht
    lauf_pfad = os.path.join(HIER, f"lauf-{stamm}.json")
    # Ein "Lauf" beginnt mit "Statistik zuruecksetzen" (cfg zaehl_ab). Gezaehlt wird nur, was danach
    # geschah — vorher las der Bot die Deals des ganzen Tages aus der Fusion-Historie wieder ein,
    # das Zuruecksetzen hielt nur Sekunden (Finn 30.09.2026).
    lauf = lies_json(lauf_pfad) or {}
    kurve_ab = {"wert": None}

    def server_versatz(jetzt):
        """Serverzeit minus echte Zeit, auf Viertelstunden gerundet (Fusion: +2 bzw. +3 h)."""
        return round(((jetzt - dt.datetime(1970, 1, 1)).total_seconds() - time.time()) / 900.0) * 900

    def tages_deals(tag, ab_server=0):
        """Eigene Deals des Servertags ab ab_server (Serverzeit-Sekunden):
        (Ergebnis inkl. Kosten, gehandeltes Volumen, Anzahl, letzte 60 fuer die Anzeige)."""
        try:
            von = dt.datetime.strptime(tag, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
            ds = mt5.history_deals_get(von, von + dt.timedelta(days=1, hours=2)) or []
        except Exception:
            return 0.0, 0.0, 0, []
        ds = [d for d in ds if int(d.magic) == MAGIC and d.symbol == sym and int(d.time) >= ab_server]
        erg = sum(float(d.profit) + float(d.commission) + float(d.swap) + float(getattr(d, "fee", 0.0) or 0.0) for d in ds)
        liste = [{"zeit": dt.datetime.fromtimestamp(int(d.time), dt.timezone.utc).replace(tzinfo=None).strftime("%H:%M:%S"), "kauf": int(d.type) == 0,
                  "auf": int(getattr(d, "entry", 0)) == 0, "lot": round(float(d.volume), 2), "preis": round(float(d.price), 2),
                  "ergebnis": round(float(d.profit), 2)} for d in sorted(ds, key=lambda d: (int(d.time), int(d.ticket)))[-60:]]
        return erg, sum(float(d.volume) for d in ds), len(ds), liste

    schreibfehler = {"gemeldet": False}

    def schreibe_json(pfad, daten):
        """Windows verweigert os.replace, solange ein anderer Prozess (die Uebersicht) die Zieldatei
        gerade offen hat — dann kurz warten und erneut, notfalls direkt schreiben (30.09.2026: Long-Bot
        lief, seine Statusdatei blieb aber stehen)."""
        tmp = pfad + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(daten, f)
        except OSError as e:
            if not schreibfehler["gemeldet"]:
                L(f"(Datei {os.path.basename(pfad)} nicht schreibbar: {e})"); schreibfehler["gemeldet"] = True
            return
        for _ in range(8):
            try:
                os.replace(tmp, pfad); return
            except OSError:
                time.sleep(0.05)
        try:
            with open(pfad, "w", encoding="utf-8") as f:
                json.dump(daten, f)
        except OSError as e:
            if not schreibfehler["gemeldet"]:
                L(f"(Datei {os.path.basename(pfad)} nicht schreibbar: {e})"); schreibfehler["gemeldet"] = True

    def status_schreiben(jetzt, mitte, soll, aktiv):
        """Stand fuer die Uebersicht (dashboard.py). Reine Anzeige — ein Fehler hier darf den Bot nie stoppen."""
        try:
            k = mt5.account_info(); ps = eigene()
            ist = sum(float(p.volume) for p in ps); offen = sum(float(p.profit) + float(p.swap) for p in ps)
            tag = z.get("tag")
            versatz = server_versatz(jetzt)
            zaehl_ab = float(cfg.get("zaehl_ab") or 0.0)
            if lauf.get("ab") != zaehl_ab or not lauf.get("seit"):
                # Neuer Lauf: Equity jetzt ist die Null-Linie, Grid-Runden zaehlen ab dem aktuellen Stand.
                lauf.clear()
                lauf.update({"ab": zaehl_ab, "seit": zaehl_ab or time.time(), "equity_start": float(k.equity) if k else 0.0,
                             "basis": {"tag": tag, "hoch": int(z.get("hoch", 0)), "runter": int(z.get("runter", 0))}, "runden_vorher": 0,
                             "runden_tage": {}})
                schreibe_json(lauf_pfad, lauf)
            ab_server = int(lauf["seit"] + versatz)
            real, vol, anzahl, deal_liste = tages_deals(tag, ab_server) if tag else (0.0, 0.0, 0, [])
            b = lauf.get("basis") or {}
            bh, br = (b.get("hoch", 0), b.get("runter", 0)) if b.get("tag") == tag else (0, 0)
            runden = max(0, min(int(z.get("hoch", 0)) - bh, int(z.get("runter", 0)) - br))
            if tag and lauf["runden_tage"].get(tag) != runden:
                lauf["runden_tage"][tag] = runden
                schreibe_json(lauf_pfad, lauf)
            lauf_runden = sum(lauf["runden_tage"].values())
            try:
                ld = mt5.history_deals_get(dt.datetime.fromtimestamp(ab_server, dt.timezone.utc), jetzt.replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)) or []
            except Exception:
                ld = []
            ld = [d for d in ld if int(d.magic) == MAGIC and d.symbol == sym and int(d.time) >= ab_server]
            lauf_volumen = sum(float(d.volume) for d in ld)
            schritt_punkte = float(z.get("anker") or 0.0) * cfg["schritt_prozent"] / 100.0
            # Was die Grid-Runden gebracht haben: je Runde schritt_lot ueber eine Stufe. Der Rest des
            # Tagesergebnisses kommt aus dem Bestand (Start-Position), der mit dem Markt laeuft.
            grid_ertrag = runden * cfg["schritt_lot"] * schritt_punkte * punktwert
            if kurve["tag"] != tag or kurve_ab["wert"] != lauf["ab"]:
                kurve["tag"] = tag; kurve["punkte"] = []; kurve_ab["wert"] = lauf["ab"]
            minute = jetzt.hour * 60 + jetzt.minute
            if tag and (not kurve["punkte"] or kurve["punkte"][-1][0] != minute):
                kurve["punkte"].append([minute, round(real + offen, 2)])
            schreibe_json(status_pfad, {
                "bot": cfg["richtung"], "konto": int(k.login) if k else None, "waehrung": getattr(k, "currency", ""),
                "demo": bool(k) and int(getattr(k, "trade_mode", -1)) == 0,
                "scharf": bool(cfg["scharf"]), "laeuft": bool(cfg.get("laeuft", True)), "version": version, "geschrieben": time.time(),
                "serverzeit": jetzt.strftime("%Y-%m-%d %H:%M:%S"), "kurs": round(mitte, 2),
                "tag": tag, "aktiv": bool(aktiv), "anker": z.get("anker"), "stufe": z.get("cur", 0),
                "soll_lot": soll, "ist_lot": round(ist, 2), "positionen": len(ps),
                "offen": round(offen, 2), "realisiert": round(real, 2), "tagesergebnis": round(real + offen, 2),
                "volumen": round(vol, 2), "deals": anzahl,
                "runden": runden, "grid_ertrag": round(grid_ertrag, 2), "bestand_ergebnis": round(real + offen - grid_ertrag, 2),
                "stufe_min": z.get("min", 0), "stufe_max": z.get("max", 0), "punktwert": round(punktwert, 4),
                "positionen_liste": [{"ticket": int(p.ticket), "lot": round(float(p.volume), 2), "preis": round(float(p.price_open), 2),
                                      "ergebnis": round(float(p.profit), 2),
                                      "zeit": dt.datetime.fromtimestamp(int(p.time), dt.timezone.utc).replace(tzinfo=None).strftime("%H:%M:%S")}
                                     for p in sorted(ps, key=lambda p: -float(p.volume))[:80]],
                "deals_liste": deal_liste,
                "guthaben": round(float(k.balance), 2) if k else None, "equity": round(float(k.equity), 2) if k else None,
                "margin": round(float(k.margin), 2) if k else None, "margin_level": round(float(k.margin_level), 1) if k and k.margin else None,
                "start": cfg["start"], "ende": cfg["ende"], "start_lot": cfg["start_lot"], "schritt_lot": cfg["schritt_lot"],
                "schritt_prozent": cfg["schritt_prozent"], "kurve": kurve["punkte"][-1440:],
                "lauf_seit": lauf["seit"], "lauf_equity_start": round(lauf["equity_start"], 2),
                "lauf_ergebnis": round(float(k.equity) - lauf["equity_start"], 2) if k else None,
                "lauf_volumen": round(lauf_volumen, 2), "lauf_deals": len(ld), "lauf_runden": lauf_runden})
            # Abgeschlossenen Tag einmal ins Tagesbuch: Tag beendet und nichts mehr offen.
            if tag and z.get("fertig") and not ps:
                try:
                    with open(verlauf_pfad, "r", encoding="utf-8") as f:
                        buch = json.load(f)
                except (OSError, ValueError):
                    buch = []
                if not any(e.get("tag") == tag for e in buch):
                    buch.append({"tag": tag, "ergebnis": round(real, 2), "volumen": round(vol, 2), "deals": anzahl,
                                 "runden": runden, "grid_ertrag": round(grid_ertrag, 2),
                                 "stufe_min": z.get("min", 0), "stufe_max": z.get("max", 0),
                                 "anker": z.get("anker"), "schluss_stufe": z.get("cur", 0), "guthaben": round(float(k.balance), 2) if k else None})
                    schreibe_json(verlauf_pfad, buch[-400:])
        except Exception as e:
            L(f"(Status nicht geschrieben: {type(e).__name__})")

    cfg_stand = os.path.getmtime(cfg_pfad)
    naechste_kontrolle = time.time() + 5.0
    letzter_status = 0.0
    letzte_meldung = None
    pause_bis = 0.0
    letzter_tick = 0
    version = lokale_version()
    naechste_pruefung = time.time() + UPDATE_TAKT_S
    L(f"Version {version or '?'}")
    while True:
        time.sleep(float(cfg["poll_interval"]))
        if time.time() >= naechste_kontrolle:
            naechste_kontrolle = time.time() + 5.0
            # Einstellungen geaendert (Uebersicht oder Editor): neu starten, damit die neuen Werte gelten.
            try:
                if os.path.getmtime(cfg_pfad) != cfg_stand:
                    L("Einstellungen geaendert — Neustart mit den neuen Werten")
                    mt5.shutdown(); sys.exit(0)
            except OSError:
                pass
            # Im Terminal ein anderes Konto eingeloggt (z. B. Demo -> Live umgestellt): sofort aufhoeren.
            k_jetzt = mt5.account_info()
            if k_jetzt is not None and int(k_jetzt.login) != int(cfg["expected_login"]):
                L(f"⛔ Im Terminal ist jetzt Konto {k_jetzt.login} eingeloggt, eingestellt ist {cfg['expected_login']} — keine Order mehr, Neustart")
                mt5.shutdown(); sys.exit(1)
        if time.time() >= naechste_pruefung:
            naechste_pruefung = time.time() + UPDATE_TAKT_S
            # Update ueber update.py (laedt ueber die Commit-Kennung). Neu gestartet wird nur, wenn danach
            # die lokale VERSION wirklich eine andere ist — der Vergleich mit .../main/VERSION allein hat
            # wegen GitHubs 5-Minuten-Zwischenspeicher unnoetige Neustarts ausgeloest (30.09.2026).
            try:
                import importlib, update
                importlib.reload(update)
                update.lauf(leise=True)
            except Exception:
                pass
            neu = lokale_version()
            if neu and version and neu != version:
                L(f"neue Version {neu} (lief mit {version}) — Neustart zum Aktualisieren")
                mt5.shutdown(); sys.exit(0)
        tick = mt5.symbol_info_tick(sym)
        if tick is None or not tick.bid or not tick.ask:
            continue
        # Serverzeit aus dem Tick. Ohne neuen Tick (Markt zu) bleibt die Zeit stehen —
        # dann wird auch nichts gesendet.
        if int(tick.time) == letzter_tick and z.get("fertig") is not False:
            # Markt steht: nichts zu tun, aber die Uebersicht soll sehen, dass der Bot lebt.
            if time.time() - letzter_status >= 15.0:
                letzter_status = time.time()
                status_schreiben(dt.datetime.fromtimestamp(int(tick.time), dt.timezone.utc).replace(tzinfo=None), (tick.bid + tick.ask) / 2.0, 0.0, False)
            continue
        letzter_tick = int(tick.time)
        jetzt = dt.datetime.fromtimestamp(int(tick.time), dt.timezone.utc).replace(tzinfo=None)
        heute = jetzt.strftime("%Y-%m-%d"); minute = jetzt.hour * 60 + jetzt.minute
        mitte = (tick.bid + tick.ask) / 2.0
        vorher = json.dumps(z, sort_keys=True)
        z, aktiv, ereignis = naechster_zustand(z, heute, minute, mitte, cfg)
        if not cfg.get("laeuft", True):
            aktiv = False                      # gestoppt: Soll 0, offene Positionen werden geschlossen
        if ereignis:
            L(ereignis)
        if json.dumps(z, sort_keys=True) != vorher:
            try:
                with open(zustand_pfad, "w", encoding="utf-8") as f:
                    json.dump(z, f)
            except OSError:
                pass
        soll = soll_volumen(cfg["richtung"], cfg["start_lot"], cfg["schritt_lot"], z.get("cur", 0), cfg["max_lot"], vol_step) if aktiv else 0.0
        if time.time() - letzter_status >= 3.0:
            letzter_status = time.time()
            status_schreiben(jetzt, mitte, soll, aktiv)
        if time.time() < pause_bis:
            continue
        ps = eigene()
        # Nur Positionen in Bot-Richtung zaehlen; eine fremde Richtung mit unserer Magic gibt es nicht.
        plan = abgleich_plan([(int(p.ticket), float(p.volume)) for p in ps], soll, vol_step, vol_max)
        if not plan:
            continue
        if not cfg["scharf"]:
            meldung = f"Trockenlauf: Soll {soll:.2f} Lot, Ist {sum(p.volume for p in ps):.2f} → wuerde {plan}"
            if meldung != letzte_meldung:
                L(meldung); letzte_meldung = meldung
            continue
        for auftrag in plan:
            tick = mt5.symbol_info_tick(sym)
            if auftrag[0] == "auf":
                typ = mt5.ORDER_TYPE_BUY if kauf_richtung else mt5.ORDER_TYPE_SELL
                req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": auftrag[1], "type": typ,
                       "price": tick.ask if kauf_richtung else tick.bid, "deviation": int(cfg["deviation_points"]),
                       "magic": MAGIC, "comment": f"grid {z.get('cur', 0):+d}",
                       "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling}
                ok = senden(req, f"{'Kauf' if kauf_richtung else 'Verkauf'} {auftrag[1]:.2f} (auf)")
            else:
                typ = mt5.ORDER_TYPE_SELL if kauf_richtung else mt5.ORDER_TYPE_BUY
                req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": auftrag[2], "type": typ,
                       "position": auftrag[1], "price": tick.bid if kauf_richtung else tick.ask,
                       "deviation": int(cfg["deviation_points"]), "magic": MAGIC, "comment": f"grid {z.get('cur', 0):+d}",
                       "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling}
                ok = senden(req, f"{'Verkauf' if kauf_richtung else 'Kauf'} {auftrag[2]:.2f} (zu, Ticket {auftrag[1]})")
            if not ok:
                # Abgelehnt (Markt zu, kein Geld, Handel aus): 5 s warten statt je Durchlauf neu zu senden.
                pause_bis = time.time() + 5.0
                break


if __name__ == "__main__":
    main()
