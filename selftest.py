# -*- coding: utf-8 -*-
"""Selbsttest der Grid-Logik ohne MT5: python selftest.py"""
from grid import stufe_nachfuehren, soll_volumen, naechster_zustand, abgleich_plan, STANDARD, runde

cfg = dict(STANDARD)
ok = 0
def pruefe(name, ist, soll):
    global ok
    assert ist == soll, f"{name}: {ist!r} statt {soll!r}"
    ok += 1

# Stufen: erst zaehlen, wenn erreicht; zurueck erst eine ganze Stufe tiefer
pruefe("bleibt", stufe_nachfuehren(30000, 0.1, 0, 30029), 0)
pruefe("hoch 1", stufe_nachfuehren(30000, 0.1, 0, 30030), 1)
pruefe("kein Flattern", stufe_nachfuehren(30000, 0.1, 1, 30005), 1)
pruefe("zurueck", stufe_nachfuehren(30000, 0.1, 1, 30000), 0)
pruefe("Sprung", stufe_nachfuehren(30000, 0.1, 0, 29850), -5)

# Soll-Volumen wie von Finn beschrieben
pruefe("long Start", soll_volumen("long", 1.0, 0.01, 0, 2.0), 1.0)
pruefe("long +3 Stufen", soll_volumen("long", 1.0, 0.01, 3, 2.0), 0.97)
pruefe("long −2 Stufen", soll_volumen("long", 1.0, 0.01, -2, 2.0), 1.02)
pruefe("short Start", soll_volumen("short", 1.0, 0.01, 0, 2.0), 1.0)
pruefe("short +3 Stufen", soll_volumen("short", 1.0, 0.01, 3, 2.0), 1.03)
pruefe("short −2 Stufen", soll_volumen("short", 1.0, 0.01, -2, 2.0), 0.98)
pruefe("long nie negativ", soll_volumen("long", 1.0, 0.01, 150, 2.0), 0.0)
pruefe("Deckel", soll_volumen("short", 1.0, 0.01, 500, 2.0), 2.0)

# Abgleich: Start, Verkauf aus der grossen Position, Nachkauf, Abbau kleiner zuerst, Tagesende
pruefe("Start", abgleich_plan([], 1.0, 0.01), [("auf", 1.0)])
pruefe("Teilverkauf", abgleich_plan([(7, 1.0)], 0.99, 0.01), [("zu", 7, 0.01)])
pruefe("Nachkauf", abgleich_plan([(7, 1.0)], 1.01, 0.01), [("auf", 0.01)])
pruefe("klein zuerst", abgleich_plan([(7, 1.0), (8, 0.01), (9, 0.01)], 0.99, 0.01), [("zu", 8, 0.01), ("zu", 9, 0.01), ("zu", 7, 0.01)])
pruefe("Ende", abgleich_plan([(7, 0.97), (8, 0.01)], 0.0, 0.01), [("zu", 8, 0.01), ("zu", 7, 0.97)])
pruefe("passt", abgleich_plan([(7, 1.0)], 1.0, 0.01), [])
pruefe("Maximal-Lot teilt", abgleich_plan([], 1.0, 0.01, 0.4), [("auf", 0.4), ("auf", 0.4), ("auf", 0.2)])

# Ein ganzer Tag gegen ein simuliertes Konto, Long und Short
for richtung in ("long", "short"):
    c = dict(cfg, richtung=richtung)
    z = {}; pos = []; nr = 0
    def lauf(heute, minute, kurs):
        global z, pos, nr
        z, aktiv, _ = naechster_zustand(z, heute, minute, kurs, c)
        soll = soll_volumen(richtung, 1.0, 0.01, z.get("cur", 0), 2.0) if aktiv else 0.0
        for a in abgleich_plan(pos, soll, 0.01):
            if a[0] == "auf": nr += 1; pos.append((nr, a[1]))
            else: pos = [(t, runde(v - a[2], 0.01)) if t == a[1] else (t, v) for t, v in pos]; pos = [p for p in pos if p[1] > 1e-9]
        return runde(sum(v for _, v in pos), 0.01)
    pruefe(f"{richtung} vor Start", lauf("2026-10-01", 30, 30000), 0.0)
    pruefe(f"{richtung} Start", lauf("2026-10-01", 61, 30000), 1.0)
    pruefe(f"{richtung} +0,2 %", lauf("2026-10-01", 120, 30061), 0.98 if richtung == "long" else 1.02)
    pruefe(f"{richtung} zurueck zum Anker", lauf("2026-10-01", 180, 29999), 1.0)
    pruefe(f"{richtung} −0,3 %", lauf("2026-10-01", 240, 29909), 1.03 if richtung == "long" else 0.97)
    pruefe(f"{richtung} Tagesende", lauf("2026-10-01", 23 * 60, 29950), 0.0)
    pruefe(f"{richtung} kein Neustart am selben Tag", lauf("2026-10-01", 23 * 60 + 30, 29950), 0.0)
    pruefe(f"{richtung} naechster Tag", lauf("2026-10-02", 61, 30200), 1.0)
    pruefe(f"{richtung} neuer Anker", z["anker"], 30200)
print(f"alle {ok} Pruefungen bestanden")
