# -*- coding: utf-8 -*-
"""einrichten.py — fragt je Bot nach Terminal und Kontonummer, schreibt config-long.json und
config-short.json (immer mit scharf=false) und prueft auf Wunsch die Verbindung.
Aufruf: einrichten.bat"""
import json, os, sys

HIER = os.path.dirname(os.path.abspath(__file__))


def terminal_aus_eingabe(text):
    """Nimmt, was der Nutzer einfuegt: die terminal64.exe selbst, den Installationsordner oder den
    Datenordner (MT5: Datei -> Dateiordner oeffnen) — dort steht der Installationsordner in origin.txt."""
    p = text.strip().strip('"').strip("'").strip()
    if not p:
        return None, "leer"
    if p.lower().endswith("terminal64.exe"):
        return (p, None) if os.path.isfile(p) else (None, "Datei nicht gefunden")
    if os.path.isdir(p):
        exe = os.path.join(p, "terminal64.exe")
        if os.path.isfile(exe):
            return exe, None
        origin = os.path.join(p, "origin.txt")
        if os.path.isfile(origin):
            for enc in ("utf-16", "utf-8-sig", "cp1252"):
                try:
                    with open(origin, "r", encoding=enc) as f:
                        ziel = f.read().strip().strip("\x00").strip()
                    exe = os.path.join(ziel, "terminal64.exe")
                    if os.path.isfile(exe):
                        return exe, None
                except (OSError, UnicodeError):
                    continue
        return None, "in diesem Ordner liegt keine terminal64.exe"
    return None, "Ordner nicht gefunden"


def frage_bot(name):
    print(f"\n=== {name}-Bot ===")
    while True:
        exe, fehler = terminal_aus_eingabe(input(f"Pfad zum MT5 des {name}-Kontos (terminal64.exe oder Ordner): "))
        if exe:
            print(f"  gefunden: {exe}")
            break
        print(f"  {fehler} — bitte noch einmal.")
    while True:
        nr = input(f"Kontonummer des {name}-Kontos: ").strip()
        if nr.isdigit() and int(nr) > 0:
            break
        print("  nur Ziffern — bitte noch einmal.")
    return exe, int(nr)


def schreibe(richtung, exe, login):
    with open(os.path.join(HIER, f"config-{richtung}.vorlage.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.pop("_hinweis", None)
    ziel = os.path.join(HIER, f"config-{richtung}.json")
    if os.path.isfile(ziel):
        # Lot- und Zeit-Werte einer vorhandenen Config behalten, nur Terminal und Konto neu setzen.
        try:
            with open(ziel, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    cfg.update({"terminal_path": exe, "expected_login": login, "richtung": richtung, "scharf": False})
    with open(ziel, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return ziel


def pruefe(richtung):
    import MetaTrader5 as mt5
    with open(os.path.join(HIER, f"config-{richtung}.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    print(f"\n--- Pruefung {richtung} ---")
    if not mt5.initialize(path=cfg["terminal_path"]):
        print(f"  ❌ keine Verbindung: {mt5.last_error()} (laeuft das Terminal, ist das Konto eingeloggt?)")
        return False
    try:
        k = mt5.account_info()
        if k is None:
            print("  ❌ kein Konto eingeloggt"); return False
        ok = int(k.login) == int(cfg["expected_login"])
        print(f"  Konto {k.login} bei {k.server}, Guthaben {k.balance:.2f} {k.currency}, Hebel 1:{k.leverage} — {'✅ passt' if ok else '❌ erwartet ' + str(cfg['expected_login'])}")
        hedging = int(getattr(k, "margin_mode", -1)) == 2
        print(f"  Kontoart: {'Hedging ✅' if hedging else 'kein Hedging-Konto ❌ (Teilverkauf funktioniert trotzdem, aber bitte melden)'}")
        t = mt5.terminal_info()
        print(f"  Algo-Trading im Terminal: {'an ✅' if t and t.trade_allowed else 'AUS ❌ (Knopf oben im Terminal anschalten)'}")
        mt5.symbol_select(cfg["symbol"], True)
        si = mt5.symbol_info(cfg["symbol"])
        if si is None:
            print(f"  ❌ Symbol {cfg['symbol']} gibt es in diesem Terminal nicht"); return False
        tick = mt5.symbol_info_tick(cfg["symbol"])
        print(f"  {cfg['symbol']}: Mindest-Lot {si.volume_min}, Lot-Schritt {si.volume_step}, Kontraktgroesse {si.trade_contract_size}, "
              f"Kurs {getattr(tick, 'bid', 0)} / {getattr(tick, 'ask', 0)}")
        if tick:
            import datetime as dt
            print(f"  Serverzeit laut letztem Tick: {dt.datetime.utcfromtimestamp(int(tick.time)):%d.%m.%Y %H:%M:%S}")
        if cfg["schritt_lot"] < si.volume_min - 1e-9:
            print(f"  ❌ schritt_lot {cfg['schritt_lot']} liegt unter dem Mindest-Lot {si.volume_min}"); ok = False
        return ok
    finally:
        mt5.shutdown()


def main():
    print("Nasdaq-Grid einrichten. Tipp: Im jeweiligen MT5 auf Datei -> 'Dateiordner oeffnen' klicken,")
    print("oben im Explorer in die Adresszeile klicken, den Pfad kopieren und hier einfuegen (Rechtsklick).")
    for richtung, name in (("long", "Long"), ("short", "Short")):
        exe, login = frage_bot(name)
        print(f"  geschrieben: {schreibe(richtung, exe, login)}")
    if input("\nVerbindung jetzt pruefen? Dabei wird nichts gehandelt. (j/n): ").strip().lower().startswith("j"):
        alles = [pruefe(r) for r in ("long", "short")]
        print("\n✅ Beide Konten erreichbar." if all(alles) else "\n❌ Mindestens eine Pruefung ist fehlgeschlagen — siehe oben.")
    print("\nNaechster Schritt: start-long.bat und start-short.bat starten (Trockenlauf, es wird noch nichts gesendet).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nabgebrochen")
