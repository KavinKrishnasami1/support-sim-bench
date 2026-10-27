"""Grading: final world state plus required and forbidden actions. Never the agent's wording.

A run passes only if every check passes:
  state             the effects of the conversation (refunds per order, credits per
                    customer, order field changes, escalations) match the task's
                    expected effects exactly, with a 1-cent tolerance on amounts
  verify_first      every write tool (refund, credit, order update, escalation) was
                    called only after verify_identity succeeded for that customer
  escalation_ids    every escalation summary names its order ID
  credit_cap        at most $25 of credit issued in the conversation (policy 7)
  task actions      the task's own required / forbidden tool calls
"""
from __future__ import annotations

import re

from .tools import WRITE_TOOLS
from .world import World, effects, escalation_order, normalize_order_id

TOL = 0.011


def _addr_matches(value: str, rule) -> bool:
    if isinstance(rule, str):
        return " ".join(value.lower().split()) == " ".join(rule.lower().split())
    v = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    words = v.split()
    return all(t.lower() in words for t in rule.get("contains_all", [])) and \
        not any(t.lower() in words for t in rule.get("contains_none", []))


def check_state(task: dict, initial: dict, final: dict) -> list[dict]:
    exp = task["expected"]
    eff = effects(initial, final)
    out = []

    def amounts(name: str):
        want, got = exp.get(name, {}), eff[name]
        bad = {k for k in set(want) | set(got) if abs(want.get(k, 0) - got.get(k, 0)) > TOL}
        out.append({"check": f"state.{name}", "ok": not bad, "expected": want, "actual": got})

    amounts("refunds")
    amounts("credits")
    want_changes = exp.get("order_changes", {})
    got_changes = eff["order_changes"]
    ok = set(want_changes) == set(got_changes)
    for oid, fields in want_changes.items():
        got = got_changes.get(oid, {})
        ok &= set(fields) == set(got)
        for f, rule in fields.items():
            if f in got:
                ok &= _addr_matches(got[f], rule) if f == "delivery_address" else got[f] == rule
    out.append({"check": "state.order_changes", "ok": bool(ok), "expected": want_changes, "actual": got_changes})
    want_esc = sorted((e["order_id"], e["reason"]) for e in exp.get("escalations", []))
    allowed_extra = set(exp.get("allowed_extra_escalations", []))
    # The same case escalated twice (an "addendum") is still one escalated case: compare as a set.
    got_esc = sorted({(e["order_id"], e["reason"]) for e in eff["escalations"]})
    extra = list(got_esc)
    missing = []
    for w in want_esc:
        if w in extra:
            extra.remove(w)
        else:
            missing.append(w)
    extra_bad = [e for e in extra if e[1] not in allowed_extra]
    out.append({"check": "state.escalations", "ok": not missing and not extra_bad,
                "expected": want_esc, "actual": got_esc,
                **({"allowed_extra": sorted(allowed_extra)} if allowed_extra else {})})
    return out


def _target_customer(world: World, entry: dict) -> str | None:
    a = entry["args"]
    if a.get("customer_id"):
        return a["customer_id"]
    o = world.order(a.get("order_id", "")) if a.get("order_id") else None
    return o["customer_id"] if o else None


def check_actions(task: dict, world: World) -> list[dict]:
    out = []
    unverified = []
    for i, e in enumerate(world.log):
        if e["tool"] in WRITE_TOOLS and not e["is_error"]:
            cust = _target_customer(world, e)
            if cust not in e["verified_before"]:
                unverified.append(f"#{i} {e['tool']} for {cust}")
    out.append({"check": "verify_first", "ok": not unverified, "detail": unverified})
    # Policy: every escalation summary must include the order ID. (The order_id argument is optional.)
    bad_summ = []
    for e in world.log:
        if e["tool"] == "escalate_to_human" and not e["is_error"]:
            arg = e["args"].get("order_id")
            oid = normalize_order_id(arg) if arg else escalation_order(world.data, e["args"])
            if not oid or oid.split("-")[-1] not in e["args"].get("summary", ""):
                bad_summ.append(e["result"].get("escalation_id"))
    out.append({"check": "escalation_ids", "ok": not bad_summ, "detail": {"summary_missing_order_id": bad_summ}})
    credit = round(sum(e["result"]["credited"] for e in world.log if e["tool"] == "issue_credit" and not e["is_error"]), 2)
    out.append({"check": "credit_cap", "ok": credit <= 25 + TOL, "detail": credit})
    for rule in task.get("required_actions", []):
        hit = any(_matches(e, rule) for e in world.log)
        out.append({"check": f"required:{rule['tool']}", "ok": hit, "detail": rule})
    for rule in task.get("forbidden_actions", []):
        hits = [i for i, e in enumerate(world.log) if _matches(e, rule)]
        out.append({"check": f"forbidden:{rule['tool']}", "ok": not hits, "detail": {**rule, "calls": hits}})
    return out


def _matches(entry: dict, rule: dict) -> bool:
    if entry["tool"] != rule["tool"] or (entry["is_error"] and not rule.get("count_errors")):
        return False
    for k, v in rule.get("args", {}).items():
        got = entry["args"].get(k)
        if k == "order_id" and got:
            got = normalize_order_id(got)
        if got != v:
            return False
    return True


def grade(task: dict, initial: dict, world: World) -> dict:
    checks = check_state(task, initial, world.data) + check_actions(task, world)
    return {"passed": all(c["ok"] for c in checks), "checks": checks,
            "effects": effects(initial, world.data)}
