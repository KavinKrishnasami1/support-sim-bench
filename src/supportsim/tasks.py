"""Load tasks and check them without any model.

`check_task` replays a task's oracle actions (what a perfect agent would do) and
each of its named mistakes through the real tools and grader. The oracle must
pass and every mistake must fail; otherwise the task or the grader has a hole.
"""
from __future__ import annotations

import copy
import json

from .grader import grade
from .tools import call_tool
from .world import ROOT, load_world

TASK_DIR = ROOT / "tasks"


def load_tasks(ids: list[str] | None = None) -> list[dict]:
    tasks = [json.loads(p.read_text()) for p in sorted(TASK_DIR.glob("T*.json"))]
    if ids:
        want = {i.upper() for i in ids}
        tasks = [t for t in tasks if t["id"] in want]
        missing = want - {t["id"] for t in tasks}
        if missing:
            raise SystemExit(f"Unknown task ids: {sorted(missing)}")
    return tasks


def replay(task: dict, actions: list[dict]) -> dict:
    world = load_world(task.get("world_patch"))
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
    for m in task.get("mistakes", []):
        if replay(task, m["actions"])["passed"]:
            problems.append(f"{task['id']}: mistake '{m['name']}' PASSES the grader")
    return problems
