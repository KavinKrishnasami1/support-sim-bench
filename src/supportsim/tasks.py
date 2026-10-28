"""Load tasks and check them without any model.

`check_task` replays a task's oracle actions (what a perfect agent would do) and
each of its named mistakes through the real tools and grader. The oracle must
pass and every mistake must fail; otherwise the task or the grader has a hole.
"""
from __future__ import annotations

import copy
import json

from .flags import rule_flags
from .grader import grade
from .tools import call_tool
from .world import SUITES, load_world


def load_tasks(ids: list[str] | None = None, suite: str = "v1") -> list[dict]:
    tasks = [{**json.loads(p.read_text()), "suite": suite}
             for p in sorted(SUITES[suite]["tasks"].glob("[TVXS][0-9]*.json"))]
    if ids:
        want = {i.upper() for i in ids}
        tasks = [t for t in tasks if t["id"] in want]
        missing = want - {t["id"] for t in tasks}
        if missing:
            raise SystemExit(f"Unknown task ids: {sorted(missing)}")
    return tasks


def replay(task: dict, actions: list[dict]) -> dict:
    world = load_world(task.get("world_patch"), task.get("suite", "v1"))
    initial = copy.deepcopy(world.data)
    for a in actions:
        call_tool(world, a["tool"], dict(a.get("args", {})))
    return grade(task, initial, world)


def check_task(task: dict) -> list[str]:
    problems = []
    g = replay(task, task["oracle"])
    if not g["passed"]:
        failed = [c["check"] for c in g["checks"] if not c["ok"]]
        problems.append(f"{task['id']}: oracle FAILS ({', '.join(failed)})")
    if g.get("security_violations"):
        problems.append(f"{task['id']}: oracle has security violations {g['security_violations']}")
    for m in task.get("mistakes", []):
        r = replay(task, m["actions"])
        if r["passed"]:
            problems.append(f"{task['id']}: mistake '{m['name']}' PASSES the grader")
            continue
        # v3 mistakes name the check they must fail on and the security violations they must trigger,
        # so a mistake that fails for an unrelated reason doesn't count as covering its target.
        failed = [c["check"] for c in r["checks"] if not c["ok"]]
        for want in m.get("fails_on", []):
            if not any(f == want or f.startswith(want + ":") for f in failed):
                problems.append(f"{task['id']}: mistake '{m['name']}' doesn't fail on {want} (failed: {failed})")
        codes = {v["code"] for v in r.get("security_violations", [])}
        for want in m.get("violates", []):
            if want not in codes:
                problems.append(f"{task['id']}: mistake '{m['name']}' doesn't trigger {want} (got: {sorted(codes)})")
        if "violates" in m and not m["violates"] and codes:
            problems.append(f"{task['id']}: mistake '{m['name']}' unexpectedly triggers {sorted(codes)}")
    return problems


def regrade_dir(run_dir) -> list[tuple]:
    """Replay each saved run's tool calls against a fresh world and grade with the current grader.

    Tool calls are deterministic given the world, so this reproduces the run's final state exactly
    without calling any model. Returns the runs whose pass/fail changed."""
    suite = json.loads((run_dir / "config.json").read_text()).get("suite", "v1")
    tasks = {t["id"]: t for t in load_tasks(suite=suite)}
    changed = []
    for p in sorted((run_dir / "runs").glob("*.json")):
        r = json.loads(p.read_text())
        if not r["completed"]:
            continue
        g = replay(tasks[r["task_id"]], [{"tool": e["tool"], "args": e["args"]} for e in r["tool_log"]])
        if g["passed"] != r["passed"]:
            changed.append((r["task_id"], r["trial"], r["passed"], g["passed"]))
            r.setdefault("grade_history", []).append(r["grade"])
        r["grade"], r["passed"] = g, g["passed"]
        # Recompute rule-based simulator flags; keep the judge's (they came from a model call).
        r["flags"] = rule_flags(tasks[r["task_id"]], r["events"]) + [f for f in r["flags"] if f["type"].startswith("judge:")]
        p.write_text(json.dumps(r, indent=1, default=str) + "\n")
    return changed
