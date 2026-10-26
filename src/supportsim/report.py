"""Summaries: pass rate and pass^k per task and overall.

pass^k is the chance that k independent trials of a task ALL succeed. With n
completed trials and c successes it is estimated as C(c, k) / C(n, k), which is
exactly "succeeded on all k" when n == k. The overall figure averages tasks.
Runs that could not be graded (API error, cost cap, simulator refusal) are
excluded and counted separately.
"""
from __future__ import annotations

import json
from collections import Counter
from math import comb
from pathlib import Path


def load_runs(run_dir: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((run_dir / "runs").glob("*.json"))]


def pass_hat_k(n: int, c: int, k: int) -> float | None:
    return comb(c, k) / comb(n, k) if n >= k else None


def summarize(run_dir: Path) -> dict:
    runs = load_runs(run_dir)
    config = json.loads((run_dir / "config.json").read_text())
    k = config.get("k") or max((r["trial"] for r in runs), default=0) + 1
    by_task: dict[str, list[dict]] = {}
    for r in runs:
        by_task.setdefault(r["task_id"], []).append(r)
    tasks = {}
    for tid, rs in sorted(by_task.items()):
        done = [r for r in rs if r["completed"]]
        n, c = len(done), sum(r["passed"] for r in done)
        failed_checks = Counter(ch["check"] for r in done if not r["passed"] for ch in r["grade"]["checks"] if not ch["ok"])
        tasks[tid] = {"n": n, "passed": c, "pass_rate": c / n if n else None,
                      **{f"pass^{j}": pass_hat_k(n, c, j) for j in range(1, k + 1)},
                      "not_graded": len(rs) - n, "flagged_runs": sum(bool(r["flags"]) for r in rs),
                      "failed_checks": dict(failed_checks.most_common())}
    graded = [t for t in tasks.values() if t["n"]]
    overall = {f"pass^{j}": (sum(t[f"pass^{j}"] for t in graded if t[f"pass^{j}"] is not None)
                             / max(1, sum(t[f"pass^{j}"] is not None for t in graded)))
               for j in range(1, k + 1)}
    overall["pass_rate"] = (sum(t["passed"] for t in graded) / sum(t["n"] for t in graded)) if graded else None
    summary = {
        "config": config, "k": k, "tasks": tasks, "overall": overall,
        "runs": len(runs), "graded_runs": sum(r["completed"] for r in runs),
        "end_reasons": dict(Counter(r["end_reason"] for r in runs)),
        "flagged_runs": sum(bool(r["flags"]) for r in runs),
        "flag_types": dict(Counter(f["type"] for r in runs for f in r["flags"])),
        "cost_usd": round(sum(r["cost_usd"] for r in runs), 4),
        "avg_customer_turns": round(sum(r["customer_turns"] for r in runs) / max(1, len(runs)), 1),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def summary_table(s: dict) -> str:
    k = s["k"]
    head = "| Task | Trials | Passed | " + " | ".join(f"pass^{j}" for j in range(1, k + 1)) + " | Flagged | Most common failed check |"
    rows = [head, "|" + "|".join(["---"] * (5 + k)) + "|"]
    for tid, t in s["tasks"].items():
        fc = next(iter(t["failed_checks"]), "")
        rows.append(f"| {tid} | {t['n']} | {t['passed']} | " + " | ".join(_pct(t[f'pass^{j}']) for j in range(1, k + 1))
                    + f" | {t['flagged_runs']} | {fc} |")
    o = s["overall"]
    rows.append("| **All** | " + f"{s['graded_runs']} | {sum(t['passed'] for t in s['tasks'].values())} | "
                + " | ".join(f"**{_pct(o[f'pass^{j}'])}**" for j in range(1, k + 1)) + f" | {s['flagged_runs']} | |")
    return "\n".join(rows)


def print_summary(s: dict) -> None:
    c = s["config"]
    print(f"\nagent={c.get('agent_model')} customer={c.get('user_model')} k={s['k']} "
          f"graded {s['graded_runs']}/{s['runs']} runs, cost ${s['cost_usd']:.2f}")
    print(summary_table(s))
    print(f"end reasons: {s['end_reasons']}; flags: {s['flag_types'] or 'none'}")
