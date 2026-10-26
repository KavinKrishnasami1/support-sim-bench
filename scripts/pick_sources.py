"""Pick one ABCD conversation per subflow we base a task on (seeded), and print it."""
import gzip, json, random, sys
SUBFLOWS = sys.argv[1].split(",")
d = json.load(gzip.open("data/raw/abcd/abcd_v1.1.json.gz"))
convos = [c for split in ("train", "dev", "test") for c in d[split]]
for sf in SUBFLOWS:
    pool = sorted((c for c in convos if c["scenario"]["subflow"] == sf), key=lambda c: c["convo_id"])
    c = random.Random(f"supportsim:{sf}").choice(pool)
    print(f"\n=== {sf}  convo_id={c['convo_id']}  ({len(pool)} in pool)")
    for spk, text in c["original"][:40]:
        if spk != "action":
            print(f"  {spk[:4]}: {text[:150]}")
        else:
            print(f"  [action] {text[:100]}")
