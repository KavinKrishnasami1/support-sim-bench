"""Write PROVENANCE.md from the task files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tasks = [json.loads(p.read_text()) for p in sorted((ROOT / "tasks").glob("T*.json"))]
tasks += [json.loads(p.read_text()) for p in sorted((ROOT / "tasks" / "v2").glob("V*.json"))]
L = ["# Provenance", "",
     "Every task is derived from one conversation in the **Action-Based Conversations Dataset (ABCD)** by ASAPP "
     "Research ([repository](https://github.com/asappresearch/abcd), commit `6b8700ce67c6b37b062dd7a60abc76d7ef832a97`, "
     "MIT license, Copyright (c) 2021 ASAPP Research). ABCD has about 10,000 human-to-human customer-service chats "
     "for a clothing retailer, each labelled with a policy-constrained flow such as refunds, order status, address "
     "changes and billing disputes.", "",
     "**What we took from the source conversations:** the shape of the customer's behaviour (vague openings, details "
     "given one at a time, corrections, impatience with verification, third parties, pushback). **What we did not "
     "take:** any text, names, addresses, order numbers or the agents' actions. The ABCD agents sometimes break their "
     "own policy (for example crediting money back without checks), so the source chats are not used as labels. "
     "Every task was rewritten for food delivery with invented people, restaurants, orders and amounts.", "",
     "The raw ABCD files are not in this repository. `scripts/download_abcd.sh` fetches the pinned version "
     "(SHA-256 checked), and `python scripts/show_source.py T05` prints the source chat for a task.", "",
     "| Task | Title | ABCD convo | Flow / subflow | License | What we took |", "|---|---|---|---|---|---|"]
for t in tasks:
    s = t["source"]
    L.append(f"| {t['id']} | {t['title']} | {s['convo_id']} | {s['flow']} / {s['subflow']} | {s['license']} | {s['what_we_took']} |")
L += ["", "The worlds (`world/base.json`, `world/v2/base.json`) and policies (`world/policy.md`, `world/v2/policy.md`) "
      "were written for this benchmark. All people, contact details and addresses in them are invented. Several v2 "
      "tasks reuse an ABCD conversation already used in v1 for a different customer behaviour."]
(ROOT / "PROVENANCE.md").write_text("\n".join(L) + "\n")
print("wrote PROVENANCE.md")
