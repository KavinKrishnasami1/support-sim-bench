"""World state: the food-delivery database a task starts from, loaded fresh per run.

The world is plain JSON (world/base.json) plus an optional per-task patch. Tools
read and write it; the grader compares the final state with the initial state.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Each suite has its own world, policy and task folder. v1 is the original 13 tasks.
SUITES = {
    "v1": {"world": ROOT / "world" / "base.json", "policy": ROOT / "world" / "policy.md", "tasks": ROOT / "tasks"},
    "v2": {"world": ROOT / "world" / "v2" / "base.json", "policy": ROOT / "world" / "v2" / "policy.md",
           "tasks": ROOT / "tasks" / "v2"},
}


@dataclass
class World:
    data: dict
    log: list[dict] = field(default_factory=list)       # every tool call, in order
    verified: set[str] = field(default_factory=set)      # customer_ids verified this conversation
    failed_verifications: dict[str, int] = field(default_factory=dict)

    @property
    def now(self) -> datetime:
        return datetime.fromisoformat(self.data["now"])

    def customer(self, customer_id: str) -> dict | None:
        return next((c for c in self.data["customers"] if c["customer_id"] == customer_id), None)

    def order(self, order_id: str) -> dict | None:
        """Find an order by its number, whatever prefix or punctuation the caller used ("7101", "Q-7101", "#7101")."""
        digits = re.sub(r"\D", "", str(order_id or ""))
        return next((o for o in self.data["orders"] if digits and re.sub(r"\D", "", o["order_id"]) == digits), None)

    def orders_of(self, customer_id: str) -> list[dict]:
        return [o for o in self.data["orders"] if o["customer_id"] == customer_id]


def normalize_order_id(order_id: str) -> str:
    """Canonical form for comparing IDs: "5102", "o5102", "#5102" -> "O-5102"; "q7101" -> "Q-7101"."""
    digits = re.sub(r"\D", "", str(order_id))
    m = re.match(r"\s*#?\s*([A-Za-z])", str(order_id))
    return f"{m.group(1).upper() if m else 'O'}-{digits}" if digits else str(order_id)


def _merge(base, patch):
    """Deep-merge a patch. Lists of records are merged by their *_id key."""
    if isinstance(base, dict) and isinstance(patch, dict):
        for k, v in patch.items():
            base[k] = _merge(base.get(k), v) if k in base else v
        return base
    if isinstance(base, list) and isinstance(patch, list) and patch and isinstance(patch[0], dict):
        key = next((k for k in patch[0] if k.endswith("_id")), None)
        if key:
            by_id = {r.get(key): r for r in base}
            for rec in patch:
                if rec.get(key) in by_id:
                    _merge(by_id[rec[key]], rec)
                else:
                    base.append(rec)
            return base
    return patch


def load_world(patch: dict | None = None, suite: str = "v1") -> World:
    data = json.loads(SUITES[suite]["world"].read_text())
    if patch:
        data = _merge(data, copy.deepcopy(patch))
    return World(data)


def policy_text(suite: str = "v1") -> str:
    return SUITES[suite]["policy"].read_text()


# ---------------------------------------------------------------------------
# Effects: what changed between two states, in the terms the grader checks
# ---------------------------------------------------------------------------
def effects(initial: dict, final: dict) -> dict:
    def refunds(d):
        return {o["order_id"]: round(sum(r["amount"] for r in o["refunds"]), 2) for o in d["orders"]}

    def credits(d):
        return {c["customer_id"]: round(sum(e["amount"] for e in c["credit_ledger"]), 2) for c in d["customers"]}

    r0, r1 = refunds(initial), refunds(final)
    c0, c1 = credits(initial), credits(final)
    o0 = {o["order_id"]: o for o in initial["orders"]}
    changes = {}
    for o in final["orders"]:
        before = o0.get(o["order_id"], {})
        diff = {k: o[k] for k in ("status", "delivery_address") if before.get(k) != o.get(k)}
        if diff:
            changes[o["order_id"]] = diff
    return {
        "refunds": {k: round(v - r0.get(k, 0), 2) for k, v in r1.items() if round(v - r0.get(k, 0), 2)},
        "credits": {k: round(v - c0.get(k, 0), 2) for k, v in c1.items() if round(v - c0.get(k, 0), 2)},
        "order_changes": changes,
        "escalations": [{"order_id": escalation_order(final, e), "customer_id": e.get("customer_id"),
                         "reason": e.get("reason")}
                        for e in final["escalations"][len(initial["escalations"]):]],
    }


def escalation_order(data: dict, esc: dict) -> str | None:
    """The order an escalation is about: its order_id argument, or else the customer's
    order whose number appears in the summary (the policy asks for it in the summary)."""
    if esc.get("order_id"):
        return esc["order_id"]
    for o in data["orders"]:
        if o["customer_id"] == esc.get("customer_id") and \
                re.search(r"(?<!\d)" + o["order_id"].split("-")[-1] + r"(?!\d)", esc.get("summary", "")):
            return o["order_id"]
    return None
