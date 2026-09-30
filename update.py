# -*- coding: utf-8 -*-
"""update.py — holt den aktuellen Stand aus dem Repo, wenn dort eine andere VERSION steht.

Wird von den Start-Dateien vor jedem Start aufgerufen und von dashboard.py im Hintergrund.
GitHub liefert Dateien unter .../main/ bis zu 5 Minuten alt aus — deshalb wird bei einer
neuen VERSION erst die Commit-Kennung geholt und dann genau dieser Stand geladen. Ersetzt
wird nur, was vollstaendig ankam und (bei .py) fehlerfrei uebersetzt; VERSION zuletzt.
Configs, Zustand, Logs und die .bat-Dateien fasst er nie an."""
import json, os, sys, urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = "finntraidingview-cmd/nasdaq-grid"
DATEIEN = ["grid.py", "dashboard.py", "dashboard.html", "einrichten.py", "selftest.py", "update.py",
           "config-long.vorlage.json", "config-short.vorlage.json", "README.md"]


def hole(url, grenze=2_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": "nasdaq-grid-update"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(grenze)


def lokale_version():
    try:
        with open(os.path.join(HIER, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def repo_version():
    try:
        v = hole(f"https://raw.githubusercontent.com/{REPO}/main/VERSION", 64).decode("utf-8", "ignore").strip()
        return v if 0 < len(v) <= 40 and "<" not in v else ""
    except Exception:
        return ""


def lauf(leise=False):
    """Liefert die Liste der ersetzten Dateien ([] = nichts zu tun oder nicht moeglich)."""
    sag = (lambda *a: None) if leise else (lambda *a: print("[update]", *a, flush=True))
    fehlt = [f for f in DATEIEN if not os.path.isfile(os.path.join(HIER, f))]
    neu, alt = repo_version(), lokale_version()
    if not neu:
        sag("Repo nicht erreichbar — weiter mit dem vorhandenen Stand"); return []
    if neu == alt and not fehlt:
        return []
    try:
        sha = json.loads(hole(f"https://api.github.com/repos/{REPO}/commits/main", 200_000).decode("utf-8"))["sha"]
    except Exception as e:
        sag(f"Commit-Kennung nicht lesbar ({type(e).__name__}) — naechster Versuch spaeter"); return []
    basis = f"https://raw.githubusercontent.com/{REPO}/{sha}/"
    try:
        ziel_version = hole(basis + "VERSION", 64).decode("utf-8", "ignore").strip()
        inhalt = {f: hole(basis + f) for f in DATEIEN}
    except Exception as e:
        sag(f"Download unvollstaendig ({type(e).__name__}) — nichts ersetzt"); return []
    for f, daten in inhalt.items():
        if len(daten) < 200:
            sag(f"{f} zu klein — nichts ersetzt"); return []
        if f.endswith(".py"):
            try:
                compile(daten, f, "exec")
            except SyntaxError as e:
                sag(f"{f} fehlerhaft ({e}) — nichts ersetzt"); return []
    ersetzt = []
    for f, daten in inhalt.items():
        pfad = os.path.join(HIER, f)
        try:
            with open(pfad, "rb") as g:
                if g.read() == daten:
                    continue
        except OSError:
            pass
        with open(pfad + ".neu", "wb") as g:
            g.write(daten)
        os.replace(pfad + ".neu", pfad)
        ersetzt.append(f)
    with open(os.path.join(HIER, "VERSION.neu"), "w", encoding="utf-8") as g:
        g.write(ziel_version + "\n")
    os.replace(os.path.join(HIER, "VERSION.neu"), os.path.join(HIER, "VERSION"))
    sag(f"Version {alt or '?'} → {ziel_version}: {', '.join(ersetzt) if ersetzt else 'Dateien waren schon aktuell'}")
    return ersetzt


if __name__ == "__main__":
    try:
        lauf()
    except Exception as e:                      # ein Update-Fehler darf den Start nie verhindern
        print(f"[update] Fehler: {type(e).__name__}: {e}")
    sys.exit(0)
