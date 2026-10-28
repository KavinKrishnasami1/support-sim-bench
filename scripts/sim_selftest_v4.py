"""Simulator self-test for v4real: a scripted agent follows each task's reference solution against the real
simulated employee (claude-haiku-5-5). Prints each chat so the simulator's reactions can be read: it should accept
the valid route, react to what it noticed, follow its reveal rules and triggers, and not invent facts.

    python scripts/sim_selftest_v4.py [R01 R02 ...]  [--max-cost 0.3]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from supportsim.cli import load_dotenv
from supportsim.itsd import selftest
from supportsim.itsd.rules import Org
from supportsim.providers import AnthropicProvider, Budget, ScriptedProvider
from supportsim.runner import run_episode
from supportsim.tasks import load_tasks
from supportsim.world import load_world


def scripted_agent(task):
    org = Org(load_world(task.get("world_patch"), "v4real").data)
    calls = [{"name": a["tool"], "args": a["args"]} for a in task["oracle"]]
    _, w, _ = selftest.run(task, task["oracle"], "v4real")
    said = selftest.summary(org, task, task["oracle"], w.log)
    # Turn 1: a question; turn 2: do everything and summarise; then short replies until the employee ends.
    return ScriptedProvider(["Thanks, let me look into this. Can you tell me a bit more about what you need?",
                             {"text": "", "tool_calls": calls}, said] + ["Understood. Anything else I can help with?"] * 8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--max-cost", type=float, default=0.3)
    a = ap.parse_args()
    load_dotenv()
    user = AnthropicProvider("claude-haiku-5-5", Budget(a.max_cost))
    out = Path("results/sim_selftest_v4.json")
    rows = []
    for t in load_tasks(a.ids or None, suite="v4real"):
        r = run_episode(t, scripted_agent(t), user, max_turns=8)
        rows.append({"task": t["id"], "end_reason": r["end_reason"], "events": r["events"]})
        print(f"\n===== {t['id']} ({r['end_reason']})")
        for e in r["events"]:
            if e["role"] in ("customer", "agent", "observation"):
                print(f"  {e['role'].upper()}: {e['text'][:400]}")
    out.write_text(json.dumps(rows, indent=1) + "\n")
    print(f"\nsimulator spend ${user.budget.spent:.4f}")


if __name__ == "__main__":
    main()
