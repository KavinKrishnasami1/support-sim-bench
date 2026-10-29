"""List every non-passing v4real run in the given result dirs, with failed checks and details, for classification."""
import json, sys, glob, collections
fam = lambda c: c.split(".")[0].split(":")[0]
for d in sys.argv[1:]:
    for p in sorted(glob.glob(d + "/runs/*.json")):
        r = json.load(open(p))
        if r["passed"]:
            continue
        g = r["grade"]
        failed = [c for c in g["checks"] if not c["ok"]]
        print(f"===== {d.split('_')[-1]} {r['task_id']} t{r['trial']}: {sorted({fam(c['check']) for c in failed})}")
        for c in failed:
            if c["check"] == "say_do":
                for x in c["detail"]:
                    print(f"   SAYDO {x['kind']} {x['action']} subj={x['subject']} obj={x['object']!r} | {x['quote'][:110]}")
            elif c["check"] == "security":
                for x in c["detail"]:
                    print(f"   SV {x['code']}: {x['detail'][:120]}")
            else:
                print(f"   {c['check']}: {str(c.get('actual', c.get('detail')))[:200]}")
