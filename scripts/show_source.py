"""Print the ABCD conversation a task was derived from: python scripts/show_source.py T05"""
import gzip, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
task = next(json.loads(p.read_text()) for p in (ROOT / "tasks").glob(f"{sys.argv[1].upper()}_*.json"))
cid = task["source"]["convo_id"]
d = json.load(gzip.open(ROOT / "data/raw/abcd/abcd_v1.1.json.gz"))
convo = next(c for split in d.values() for c in split if c["convo_id"] == cid)
print(f"{task['id']} <- ABCD convo {cid} ({convo['scenario']['flow']}/{convo['scenario']['subflow']})\n")
for speaker, text in convo["original"]:
    print(f"{speaker:>8}: {text}")
