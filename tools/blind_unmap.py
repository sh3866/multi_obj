"""Un-blind: map code-keyed blind_scores_{task}.json back to real variant keys via
blind_key.json, overwrite scores_{task}.json, and print an aggregate. Run per
experiment: strongen (8 variants) or strongenall (5 variants)."""
import json, os, sys, glob

EXP = sys.argv[1] if len(sys.argv) > 1 else "strongen"
REP = {"strongen": "results/strongen/report",
       "strongenall": "results/strongenall/report"}[EXP]
AX = ["functionality", "design", "originality", "craft"]
ORDER = {"strongen": ["r0", "weak_self", "weak_fused", "weak_axes", "weak_mad",
                      "gold_fused", "gold_axes", "gold_mad"],
         "strongenall": ["r0", "SELF", "FUSED", "AXES", "MAD"]}[EXP]

key = json.load(open(f"{REP}/blind_key.json"))
tasks = sorted(key)
missing = [t for t in tasks if not os.path.exists(f"{REP}/blind_scores_{t}.json")]
if missing:
    print(f"WARNING: blind scores missing for {missing}")

def ov(d): return sum(d[a] for a in AX) / 4

agg = {v: [] for v in ORDER}
done = []
for t in tasks:
    bp = f"{REP}/blind_scores_{t}.json"
    if not os.path.exists(bp):
        continue
    bs = json.load(open(bp))
    kmap = key[t]  # code -> real variant
    real = {}
    for code, variant in kmap.items():
        if code not in bs:
            print(f"  !! {t}: code {code} ({variant}) not scored"); continue
        real[variant] = {a: bs[code][a] for a in AX}
    json.dump(real, open(f"{REP}/scores_{t}.json", "w"), indent=1)  # OVERWRITE with blind
    for v in ORDER:
        if v in real: agg[v].append(ov(real[v]))
    done.append(t)

def m(x): return sum(x) / len(x) if x else 0
print(f"\n=== {EXP} BLIND (un-blinded) — {len(done)} tasks ===")
print(f"{'variant':12} overall  | " + " ".join(f"{a[0]:>4}" for a in AX))
for v in ORDER:
    axm = [m([json.load(open(f'{REP}/scores_{t}.json'))[v][a] for t in done
             if v in json.load(open(f'{REP}/scores_{t}.json'))]) for a in AX]
    print(f"{v:12} {m(agg[v]):6.2f}   | " + " ".join(f"{x:4.1f}" for x in axm))

# per-task winner among non-r0
print("\n=== per-task best variant (excl r0) ===")
wins = {}
for t in done:
    s = json.load(open(f"{REP}/scores_{t}.json"))
    cand = [v for v in ORDER if v != "r0" and v in s]
    b = max(cand, key=lambda v: ov(s[v]))
    wins[b] = wins.get(b, 0) + 1
    print(f"  {t}: {b} ({ov(s[b]):.2f})")
print("wins:", wins)

if EXP == "strongen":
    print("\n=== best-gold vs best-weak (per task) ===")
    g = w = 0
    for t in done:
        s = json.load(open(f"{REP}/scores_{t}.json"))
        bg = max(ov(s[v]) for v in ["gold_fused", "gold_axes", "gold_mad"] if v in s)
        bw = max(ov(s[v]) for v in ["weak_self", "weak_fused", "weak_axes", "weak_mad"] if v in s)
        g += bg > bw + 0.1; w += bw > bg + 0.1
    print(f"  best-gold > best-weak: {g} | best-weak > best-gold: {w} | ties: {len(done)-g-w}")
