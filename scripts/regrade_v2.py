"""Re-grade saved IT runs (v3, v3kb, v4real) with grader v2, without touching the run files.

Each run's tool calls are replayed against a fresh world (tools are deterministic), then graded by grader v2 with
the saved chat. Claims are extracted once with claude-haiku-5-5 and cached in data/claims_cache.json.
Writes <run dir>/regrade_v2.json and prints old vs new pass/fail by category.

    python scripts/regrade_v2.py results/20261028-*  [--max-cost 0.5]
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
from pathlib import Path

from supportsim.cli import load_dotenv
from supportsim.grader import grade
from supportsim.providers import AnthropicProvider, Budget
from supportsim.tasks import load_tasks
from supportsim.tools import call_tool
from supportsim.world import load_world

FAMILIES = ["say_do", "extraneous", "order", "recovery", "goal", "task", "security"]


def family(check: str) -> str:
    return next(f for f in FAMILIES if check == f or check.startswith(f + "."))


def regrade(run_dir: Path, provider) -> list[dict]:
    cfg = json.loads((run_dir / "config.json").read_text())
    suite = cfg["suite"]
    tasks = {t["id"]: t for t in load_tasks(suite=suite)}
    rows = []
    for p in sorted((run_dir / "runs").glob("*.json")):
        r = json.loads(p.read_text())
        if not r["completed"]:
            continue
        t = tasks[r["task_id"]]
        w = load_world(t.get("world_patch"), suite)
        initial = copy.deepcopy(w.data)
        for e in r["tool_log"]:
            call_tool(w, e["tool"], e["args"])
        g = grade(t, initial, w, r["events"], provider)
        failed = sorted({family(c["check"]) for c in g["checks"] if not c["ok"]})
        rows.append({"dir": run_dir.name, "suite": suite, "model": cfg.get("agent_model"), "task": r["task_id"],
                     "trial": r["trial"], "old_passed": r["passed"], "new_passed": g["passed"],
                     "failed_families": failed, "grade": g})
    (run_dir / "regrade_v2.json").write_text(json.dumps(rows, indent=1, default=str) + "\n")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--max-cost", type=float, default=0.5)
    a = ap.parse_args()
    load_dotenv()
    prov = AnthropicProvider("claude-haiku-5-5", Budget(a.max_cost))
    rows = []
    for d in a.dirs:
        d = Path(d)
        if json.loads((d / "config.json").read_text()).get("suite") in ("v3", "v3kb", "v4real"):
            rows += regrade(d, prov)
    flips = [x for x in rows if x["old_passed"] and not x["new_passed"]]
    print(f"{len(rows)} runs re-graded; claim extraction spent ${prov.budget.spent:.4f}")
    print(f"previously passing: {sum(x['old_passed'] for x in rows)}; now failing: {len(flips)}; "
          f"previously failing now passing: {sum((not x['old_passed']) and x['new_passed'] for x in rows)}")
    c = collections.Counter(f for x in flips for f in x["failed_families"])
    print("flips by failed check family (a run can count in several):", dict(c))
    for x in flips:
        print(f"  {x['suite']:5} {x['model']:18} {x['task']} t{x['trial']}: {x['failed_families']}")


if __name__ == "__main__":
    main()
