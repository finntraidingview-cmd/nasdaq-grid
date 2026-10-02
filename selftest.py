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
    pruefe(f"{richtung} Runden", (z["hoch"], z["runter"], z["min"], z["max"]), (2, 5, -3, 2))
    pruefe(f"{richtung} Tagesende", lauf("2026-10-01", 23 * 60, 29950), 0.0)
    pruefe(f"{richtung} kein Neustart am selben Tag", lauf("2026-10-01", 23 * 60 + 30, 29950), 0.0)
    pruefe(f"{richtung} naechster Tag", lauf("2026-10-02", 61, 30200), 1.0)
    pruefe(f"{richtung} neuer Anker", z["anker"], 30200)
# Notbremse: bei ±0,3 % (6 Stufen à 0,05 %) loest Stufe 7 aus, danach Pause bis zum naechsten Tag
c2 = dict(cfg, schritt_prozent=0.05, notbremse_prozent=0.3)
zz, ak, _ = naechster_zustand({}, "2026-10-02", 61, 30000.0, c2)
zz, ak, _ = naechster_zustand(zz, "2026-10-02", 70, 30000 * 1.0030, c2)
pruefe("Bremse noch nicht", (ak, zz.get("notbremse")), (True, None))
zz, ak, ev = naechster_zustand(zz, "2026-10-02", 80, 30000 * 1.0036, c2)
pruefe("Bremse greift", (ak, zz.get("notbremse"), ev.startswith("Notbremse")), (False, True, True))
zz, ak, _ = naechster_zustand(zz, "2026-10-02", 90, 30000.0, c2)
pruefe("bleibt aus bis morgen", ak, False)
zz, ak, _ = naechster_zustand(zz, "2026-10-03", 61, 30100.0, c2)
pruefe("naechster Tag frisch", (ak, zz.get("notbremse")), (True, None))

# Grid-Gewinn aus echten Kursen: Kauf 100, Verkauf 101 = +1 je Lot; offener Rest bleibt im Stapel
from grid import grid_buchen
g1, s1, p1 = grid_buchen([], True, 100.0, 0.01)
pruefe("erst Kauf offen", (g1, s1, p1), (0.0, [[True, 100.0, 0.01]], 0))
g2, s2, p2 = grid_buchen(s1, False, 101.0, 0.01)
pruefe("Runde +1", (round(g2, 6), s2, p2), (0.01, [], 0.01))
g3, s3, _ = grid_buchen([], False, 105.0, 0.01)
g4, s4, _ = grid_buchen(s3, True, 104.0, 0.01)
pruefe("Verkauf zuerst", round(g4, 6), 0.01)
g5, s5, _ = grid_buchen([[True, 100.0, 0.01], [True, 99.0, 0.01]], False, 100.0, 0.01)
pruefe("juengster zuerst", (round(g5, 6), s5), (0.01, [[True, 100.0, 0.01]]))
g6, s6, _ = grid_buchen([[True, 100.0, 0.01]], True, 99.0, 0.01)
pruefe("gleiche Seite stapelt", (g6, len(s6)), (0.0, 2))
print(f"alle {ok} Pruefungen bestanden")
