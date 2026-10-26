"""supportsim: run the food-delivery support benchmark.

  supportsim tasks                      list tasks
  supportsim check                      replay each task's oracle and mistakes (no model calls)
  supportsim estimate [options]         print the estimated cost of a run
  supportsim run [options]              run tasks k times and grade them
  supportsim view <results dir>         write view.html for a run folder
  supportsim show <run json>            print one transcript to the terminal
  supportsim compare <dir> [<dir>...]   markdown table comparing run folders
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_AGENT = "claude-opus-5-5"
DEFAULT_USER = "claude-haiku-5-5"  # the simulated customer: a cheap model


def _models(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--agent-model", default=DEFAULT_AGENT)
    ap.add_argument("--agent-provider", default="anthropic", help="'anthropic' or module:Class")
    ap.add_argument("--agent-effort", default="medium", help="low|medium|high|xhigh|max, or 'none' to omit")
    ap.add_argument("--user-model", default=DEFAULT_USER)
    ap.add_argument("--user-provider", default="anthropic")
    ap.add_argument("--user-effort", default="low")
    ap.add_argument("--judge-model", default=DEFAULT_USER, help="model for the leak/character judge")
    ap.add_argument("--no-judge", action="store_true", help="only rule-based simulator flags")
    ap.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    ap.add_argument("-k", type=int, default=3, help="trials per task")


def main() -> None:
    ap = argparse.ArgumentParser(prog="supportsim", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tasks")
    sub.add_parser("check")
    _models(sub.add_parser("estimate"))
    r = sub.add_parser("run")
    _models(r)
    r.add_argument("--max-cost", type=float, required=True, help="hard cap in USD for the whole run")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    r.add_argument("--out", default=None)
    v = sub.add_parser("view")
    v.add_argument("dir")
    s = sub.add_parser("show")
    s.add_argument("run")
    c = sub.add_parser("compare")
    c.add_argument("dirs", nargs="+")
    a = ap.parse_args()

    from .tasks import check_task, load_tasks

    if a.cmd == "tasks":
        for t in load_tasks():
            print(f"{t['id']}  {t['title']}\n      {t['tricky']}")
    elif a.cmd == "check":
        tasks = load_tasks()
        problems = [p for t in tasks for p in check_task(t)]
        n_mistakes = sum(len(t.get("mistakes", [])) for t in tasks)
        print(f"{len(tasks)} oracles and {n_mistakes} known mistakes replayed through the grader")
        for p in problems:
            print("  PROBLEM:", p)
        print("all oracles pass and all mistakes fail" if not problems else f"{len(problems)} problems")
        sys.exit(1 if problems else 0)
    elif a.cmd in ("estimate", "run"):
        from .runner import estimate

        tasks = load_tasks(a.tasks.split(",") if a.tasks else None)
        judge = None if a.no_judge else a.judge_model
        est = estimate(tasks, a.k, a.agent_model, a.user_model, judge)
        print(f"{len(tasks)} tasks × k={a.k} = {est['runs']} runs. Estimated cost, priced as if nothing is cached "
              f"(an upper-end estimate):")
        print(f"  agent {a.agent_model}: ${est['agent']:.2f}   customer {a.user_model}: ${est['customer']:.2f}"
              + (f"   judge {judge}: ${est['judge']:.2f}" if judge else "") + f"   total ≈ ${est['total']:.2f}")
        print(f"  Likely with prompt caching: ≈ ${est['likely_with_cache']:.2f}")
        if a.cmd == "estimate":
            return
        print(f"Hard cap: ${a.max_cost:.2f}. No new API call starts once spend reaches it.")
        if est["total"] > a.max_cost:
            print("  The estimate is above the cap, so the run will probably stop early.")
        if not a.yes and input("Proceed? [y/N] ").strip().lower() != "y":
            print("Cancelled.")
            return
        from .providers import Budget, load_provider
        from .report import print_summary, summarize
        from .runner import run_batch
        from .viewer import render

        budget = Budget(a.max_cost)
        eff = lambda x: None if x == "none" else x  # noqa: E731
        agent = load_provider(a.agent_provider, a.agent_model, budget, eff(a.agent_effort))
        user = load_provider(a.user_provider, a.user_model, budget, eff(a.user_effort))
        judge_p = None if a.no_judge else load_provider("anthropic", a.judge_model, budget, "low")
        config = {k: getattr(a, k) for k in ("agent_model", "agent_effort", "user_model", "user_effort", "k",
                                              "max_cost", "agent_provider", "user_provider")}
        config.update(judge_model=judge, tasks=[t["id"] for t in tasks], estimate=est)
        out = run_batch(tasks, a.k, agent, user, judge_p, a.workers, Path(a.out) if a.out else None, config)
        summ = summarize(out)
        print_summary(summ)
        print(f"total spend (all calls incl. judge): ${budget.spent:.2f} over {budget.calls} API calls")
        summ["config"]["actual_spend_usd"] = round(budget.spent, 4)
        (out / "config.json").write_text(json.dumps(summ["config"], indent=2) + "\n")
        print(f"transcripts: {render(out)}")
    elif a.cmd == "view":
        from .viewer import render

        print(render(Path(a.dir)))
    elif a.cmd == "show":
        from .viewer import show_run

        show_run(Path(a.run))
    elif a.cmd == "compare":
        from .report import summarize

        sums = [summarize(Path(d)) for d in a.dirs]
        tids = sorted({t for s in sums for t in s["tasks"]})
        k = min(s["k"] for s in sums)
        names = [f"{s['config'].get('agent_model')} ({s['config'].get('agent_effort')})" for s in sums]
        print("| Task | " + " | ".join(f"{n} pass^1 | pass^{k}" for n in names) + " |")
        print("|---|" + "---|---|" * len(sums))
        for tid in tids:
            cells = []
            for s in sums:
                t = s["tasks"].get(tid)
                cells += ["n/a", "n/a"] if not t else [f"{t['passed']}/{t['n']}", _p(t.get(f"pass^{k}"))]
            print(f"| {tid} | " + " | ".join(cells) + " |")
        print("| **All** | " + " | ".join(f"**{_p(s['overall']['pass^1'])}** | **{_p(s['overall'][f'pass^{k}'])}**"
                                          for s in sums) + " |")


def _p(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


if __name__ == "__main__":
    main()
