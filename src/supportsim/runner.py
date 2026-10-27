"""Run episodes: one task, one simulated conversation, graded.

An episode alternates customer and agent turns. Within an agent turn the agent
may call tools any number of times (up to max_tool_steps); every text it writes
during the turn is shown to the customer as one message. The customer sees
only the agent's text, never tool calls.
"""
from __future__ import annotations

import copy
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from . import simuser
from .flags import judge_flags, rule_flags
from .grader import grade
from .providers import BudgetExceeded, ModelRefused, Provider, Usage
from .tools import call_tool, tool_specs
from .world import ROOT, load_world, policy_text

RESULTS = ROOT / "results"
COMPLETED = {"customer_ended", "max_turns", "agent_tool_loop", "agent_refused"}


def agent_system_prompt(now: str, suite: str = "v1") -> str:
    return (f"You are a customer support agent for Forkful, a food-delivery app, chatting live with a customer.\n"
            f"The current date and time is {now}.\n"
            "The customer sees only your chat messages, not your tool calls or their results. Use the tools to look "
            "things up and take actions, then tell the customer what you did.\n\n"
            f"<policy>\n{policy_text(suite)}\n</policy>")


class _Side:
    """Wraps one conversation, tagging errors with which side raised them and summing usage."""

    def __init__(self, name: str, conv):
        self.name, self.conv, self.usage = name, conv, Usage()

    def _do(self, fn, *a):
        try:
            turn = fn(*a)
        except ModelRefused as e:
            raise SideRefused(self.name, str(e)) from e
        self.usage += turn.usage
        return turn

    def send_user(self, text):
        return self._do(self.conv.send_user, text)

    def send_tool_results(self, results):
        return self._do(self.conv.send_tool_results, results)


class SideRefused(Exception):
    def __init__(self, side: str, detail: str):
        super().__init__(f"{side} refused: {detail}")
        self.side = side


def run_episode(task: dict, agent: Provider, user: Provider, max_turns: int = 20,
                max_tool_steps: int = 12) -> dict:
    suite = task.get("suite", "v1")
    world = load_world(task.get("world_patch"), suite)
    initial = copy.deepcopy(world.data)
    a = _Side("agent", agent.start(agent_system_prompt(world.data["now"], suite), tool_specs(suite)))
    u = _Side("customer", user.start(simuser.system_prompt(task["user"])))
    events: list[dict] = []
    end_reason, error = None, None
    t0 = time.time()
    try:
        msg = u.send_user(simuser.OPENING_CUE).text
        for _ in range(max_turns):
            stop = simuser.STOP_TOKEN in msg
            text = msg.replace(simuser.STOP_TOKEN, "").strip()
            if text:
                events.append({"role": "customer", "text": text})
            if stop and not text:
                end_reason = "customer_ended"
                break
            # The agent always answers the customer's last message, even a closing one ("yes, go ahead, thanks"),
            # so an approval given while leaving still gets acted on.
            turn = a.send_user(text or "(the customer sent an empty message)")
            texts, steps = [turn.text], 0
            while turn.tool_calls:
                if steps >= max_tool_steps:
                    end_reason = "agent_tool_loop"
                    break
                results = []
                for c in turn.tool_calls:
                    res, err = call_tool(world, c.name, c.args)
                    events.append({"role": "tool", "name": c.name, "args": c.args, "result": res, "is_error": err})
                    results.append((c.id, res, err))
                turn = a.send_tool_results(results)
                texts.append(turn.text)
                steps += 1
            reply = "\n\n".join(t for t in texts if t) or "(no reply)"
            events.append({"role": "agent", "text": reply})
            if stop:
                end_reason = end_reason or "customer_ended"
            if end_reason:
                break
            msg = u.send_user(reply).text
        else:
            end_reason = "max_turns"
    except BudgetExceeded as e:
        end_reason, error = "cost_cap", str(e)
    except SideRefused as e:
        end_reason, error = ("agent_refused" if e.side == "agent" else "customer_refused"), str(e)
    except Exception as e:  # API errors, malformed output: the run is not gradeable
        end_reason, error = "error", "".join(traceback.format_exception_only(e)).strip()
    result = {
        "task_id": task["id"], "end_reason": end_reason, "error": error, "seconds": round(time.time() - t0, 1),
        "events": events, "tool_log": world.log,
        "usage": {"agent": vars(a.usage), "customer": vars(u.usage)},
        "cost_usd": round(a.usage.cost(agent.model) + u.usage.cost(user.model), 5),
        "customer_turns": sum(e["role"] == "customer" for e in events),
    }
    result["completed"] = end_reason in COMPLETED
    result["grade"] = grade(task, initial, world) if result["completed"] else None
    result["passed"] = bool(result["grade"] and result["grade"]["passed"])
    result["flags"] = rule_flags(task, events)
    return result


# ---------------------------------------------------------------------------
# Cost estimate
# ---------------------------------------------------------------------------
def _tokens(s: str) -> int:
    return len(s) // 4 + 1


def estimate(tasks: list[dict], k: int, agent_model: str, user_model: str, judge_model: str | None) -> dict:
    """Rough upper-bound estimate, priced as if nothing were cached.

    Per run: T customer turns (task's est_turns), about 2 agent calls per turn
    (one with tools, one reply), agent input = system + tools + growing history,
    agent output ~600 tokens/call including thinking, customer ~250 tokens/call."""
    from .providers import PRICES

    suite = tasks[0].get("suite", "v1") if tasks else "v1"
    agent_base = _tokens(agent_system_prompt("2026-01-01T00:00:00", suite)) + _tokens(json.dumps(tool_specs(suite)))
    total = {"agent": 0.0, "customer": 0.0, "judge": 0.0}
    likely = 0.0  # same token counts, with the repeated prefix read from cache at 0.1x
    for t in tasks:
        T = t.get("est_turns", 8)
        user_base = _tokens(simuser.system_prompt(t["user"]))
        n_agent = 2 * T
        agent_in = n_agent * agent_base + 450 * n_agent * (n_agent + 1) / 2
        agent_out = 600 * n_agent
        user_in = T * user_base + 120 * T * (T + 1) / 2
        user_out = 250 * T
        pa, pu = PRICES[agent_model], PRICES[user_model]
        total["agent"] += k * (agent_in * pa[0] + agent_out * pa[1]) / 1e6
        fresh = 450 * n_agent + agent_base  # new tokens per run, written to cache once
        likely += k * ((agent_in - fresh) * pa[0] * 0.1 + fresh * pa[0] * 1.25 + agent_out * pa[1]) / 1e6
        total["customer"] += k * (user_in * pu[0] + user_out * pu[1]) / 1e6
        if judge_model:
            pj = PRICES[judge_model]
            total["judge"] += k * ((user_base + 150 * T) * pj[0] + 300 * pj[1]) / 1e6
    total["total"] = sum(total.values())
    total["likely_with_cache"] = likely + total["customer"] + total["judge"]
    total["runs"] = len(tasks) * k
    return total


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------
def run_batch(tasks: list[dict], k: int, agent: Provider, user: Provider, judge: Provider | None,
              workers: int, out_dir: Path | None = None, config: dict | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir or RESULTS / f"{stamp}_{agent.model}"
    (out / "runs").mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(config or {}, indent=2) + "\n")
    jobs = [(t, trial) for trial in range(k) for t in tasks]
    stop_all = False

    def job(t, trial):
        if stop_all:
            return None
        r = run_episode(t, agent, user)
        r["trial"] = trial
        if judge and r["completed"]:
            try:
                r["flags"] += judge_flags(judge, t, r["events"])
            except Exception as e:  # the judge is advisory; never lose a run because of it
                r["judge_error"] = str(e)
        (out / "runs" / f"{t['id']}_trial{trial}.json").write_text(json.dumps(r, indent=1, default=str) + "\n")
        return r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(job, t, trial): (t["id"], trial) for t, trial in jobs}
        for f in as_completed(futs):
            r = f.result()
            if r is None:
                continue
            mark = "PASS" if r["passed"] else ("FAIL" if r["completed"] else r["end_reason"].upper())
            fl = f" flags={len(r['flags'])}" if r["flags"] else ""
            print(f"  {r['task_id']} trial {r['trial']}: {mark}  turns={r['customer_turns']} "
                  f"${r['cost_usd']:.3f}{fl}", flush=True)
            if r["end_reason"] == "cost_cap":
                stop_all = True
    return out
