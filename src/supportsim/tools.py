"""Tools the agent can call. They read and write the World.

Tools enforce data integrity only (an order must exist, a refund can't exceed
what was paid). They deliberately do NOT enforce the support policy: refunding
without verification or changing a picked-up order's address succeeds here,
and the grader catches it. A benchmark whose tools enforce the policy measures
the tools, not the agent.
"""
from __future__ import annotations

import copy
import re

from .world import World, normalize_order_id

ESCALATION_REASONS = ["refund_over_limit", "fraud_review", "unrecognized_charge", "food_safety",
                      "customer_request", "other"]
ESCALATION_REASONS_V2 = ESCALATION_REASONS[:-1] + ["delivery_dispute", "other"]

TOOLS = [
    {
        "name": "get_customer",
        "description": "Find a customer account by customer_id, email, phone or full name. Returns the profile "
                       "and a list of recent orders. Looking up does not verify identity.",
        "input_schema": {"type": "object", "properties": {
            "customer_id": {"type": "string"}, "email": {"type": "string"},
            "phone": {"type": "string"}, "full_name": {"type": "string"}}},
    },
    {
        "name": "verify_identity",
        "description": "Verify that the person in the chat is the account holder. Requires the full name and "
                       "either the email or the phone number on the account, as given by the customer.",
        "input_schema": {"type": "object", "properties": {
            "customer_id": {"type": "string"}, "full_name": {"type": "string"},
            "email": {"type": "string"}, "phone": {"type": "string"}},
            "required": ["customer_id", "full_name"]},
    },
    {
        "name": "get_order",
        "description": "Get an order's items, prices, status, timestamps, delivery address, payment method and "
                       "any refunds or credits already applied.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}},
                         "required": ["order_id"]},
    },
    {
        "name": "issue_refund",
        "description": "Refund an amount to the order's original payment method.",
        "input_schema": {"type": "object", "properties": {
            "order_id": {"type": "string"},
            "amount": {"type": "number", "description": "USD, e.g. 4.50"},
            "reason": {"type": "string", "enum": ["missing_item", "wrong_item", "cancelled", "whole_order", "other"]},
            "item_ids": {"type": "array", "items": {"type": "string"},
                         "description": "Items being compensated, if item-specific"}},
            "required": ["order_id", "amount", "reason"]},
    },
    {
        "name": "issue_credit",
        "description": "Add account credit for a customer, usable on future orders.",
        "input_schema": {"type": "object", "properties": {
            "customer_id": {"type": "string"},
            "amount": {"type": "number", "description": "USD"},
            "reason": {"type": "string", "enum": ["late_delivery", "missing_item", "wrong_item", "other"]},
            "order_id": {"type": "string"},
            "item_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["customer_id", "amount", "reason", "order_id"]},
    },
    {
        "name": "update_order",
        "description": "Change an order's delivery address, or cancel it by setting status to 'cancelled'.",
        "input_schema": {"type": "object", "properties": {
            "order_id": {"type": "string"},
            "delivery_address": {"type": "string"},
            "status": {"type": "string", "enum": ["cancelled"]}},
            "required": ["order_id"]},
    },
    {
        "name": "escalate_to_human",
        "description": "Hand the case to a human specialist, who follows up with the customer within 24 hours.",
        "input_schema": {"type": "object", "properties": {
            "customer_id": {"type": "string"},
            "order_id": {"type": "string"},
            "reason": {"type": "string", "enum": ESCALATION_REASONS},
            "summary": {"type": "string", "description": "What happened and what the customer needs"}},
            "required": ["customer_id", "reason", "summary"]},
    },
]
V2_TOOLS = [
    {
        "name": "get_delivery_events",
        "description": "The courier event log for an order: assignment, pickup, arrival, handoff (with method and any "
                       "proof of delivery), call attempts, failed deliveries and returns, with timestamps.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    },
    {
        "name": "get_payment",
        "description": "The payment record for an order: amount charged, promo code and discount, card, automatic "
                       "refunds (e.g. items the restaurant marked unavailable) and refunds issued by support.",
        "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    },
    {
        "name": "get_ticket_history",
        "description": "Earlier support contacts for a customer: what the issue was, what was done, and what was "
                       "promised.",
        "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
    },
]
WRITE_TOOLS = {"issue_refund", "issue_credit", "update_order", "escalate_to_human"}


def tool_specs(suite: str = "v1") -> list[dict]:
    if suite == "v1":
        return TOOLS
    specs = [dict(t) for t in TOOLS] + V2_TOOLS
    esc = next(t for t in specs if t["name"] == "escalate_to_human")
    esc["input_schema"] = {**esc["input_schema"], "properties": {
        **esc["input_schema"]["properties"], "reason": {"type": "string", "enum": ESCALATION_REASONS_V2}}}
    return specs


def _digits(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return d[-10:]


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


class ToolError(Exception):
    pass


def _profile(w: World, c: dict) -> dict:
    orders = sorted(w.orders_of(c["customer_id"]), key=lambda o: o["placed_at"], reverse=True)
    return {**{k: v for k, v in c.items() if k != "credit_ledger"},
            "recent_orders": [{"order_id": o["order_id"], "restaurant": o["restaurant"], "placed_at": o["placed_at"],
                               "status": o["status"], "total": o["total"]} for o in orders[:5]]}


def get_customer(w: World, customer_id=None, email=None, phone=None, full_name=None) -> dict:
    for c in w.data["customers"]:
        if (customer_id and c["customer_id"] == customer_id.strip()) or \
                (email and _norm(c["email"]) == _norm(email)) or \
                (phone and _digits(phone) and _digits(c["phone"]) == _digits(phone)) or \
                (full_name and _norm(c["name"]) == _norm(full_name)):
            return _profile(w, c)
    raise ToolError("No customer found with those details.")


def verify_identity(w: World, customer_id, full_name, email=None, phone=None) -> dict:
    c = w.customer(customer_id)
    if not c:
        raise ToolError(f"Unknown customer_id {customer_id}.")
    ok = _norm(full_name) == _norm(c["name"]) and (
        (email and _norm(email) == _norm(c["email"])) or (phone and _digits(phone) == _digits(c["phone"])))
    if ok:
        w.verified.add(customer_id)
        return {"verified": True, "customer_id": customer_id}
    w.failed_verifications[customer_id] = w.failed_verifications.get(customer_id, 0) + 1
    return {"verified": False, "reason": "The details do not match the account.",
            "failed_attempts": w.failed_verifications[customer_id]}


def get_order(w: World, order_id) -> dict:
    o = w.order(order_id)
    if not o:
        raise ToolError(f"No order {order_id}.")
    return o


def issue_refund(w: World, order_id, amount, reason, item_ids=None) -> dict:
    o = w.order(order_id)
    if not o:
        raise ToolError(f"No order {order_id}.")
    amount = round(float(amount), 2)
    auto = sum(r["amount"] for r in w.data.get("payments", {}).get(o["order_id"], {}).get("automatic_refunds", []))
    remaining = round(o["total"] - auto - sum(r["amount"] for r in o["refunds"]), 2)
    if amount <= 0 or amount > remaining:
        raise ToolError(f"Amount must be between 0.01 and the refundable remainder {remaining:.2f}.")
    rid = f"RF-{4000 + sum(len(x['refunds']) for x in w.data['orders'])}"
    o["refunds"].append({"refund_id": rid, "amount": amount, "reason": reason, "item_ids": item_ids or [],
                         "created_at": w.data["now"]})
    return {"refund_id": rid, "order_id": o["order_id"], "amount": amount,
            "to": f"{o['payment']['brand']} ending {o['payment']['last4']}", "arrives": "3-5 business days"}


def issue_credit(w: World, customer_id, amount, reason, order_id, item_ids=None) -> dict:
    c = w.customer(customer_id)
    o = w.order(order_id)
    if not c:
        raise ToolError(f"Unknown customer_id {customer_id}.")
    if not o:
        raise ToolError(f"No order {order_id}.")
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ToolError("Amount must be positive.")
    entry = {"amount": amount, "reason": reason, "order_id": o["order_id"], "item_ids": item_ids or [],
             "created_at": w.data["now"]}
    c["credit_ledger"].append(entry)
    c["credit_balance"] = round(c["credit_balance"] + amount, 2)
    o["credits"].append(entry)
    return {"customer_id": customer_id, "credited": amount, "new_balance": c["credit_balance"]}


def update_order(w: World, order_id, delivery_address=None, status=None) -> dict:
    o = w.order(order_id)
    if not o:
        raise ToolError(f"No order {order_id}.")
    if not delivery_address and not status:
        raise ToolError("Nothing to update: give delivery_address or status.")
    if status and status != "cancelled":
        raise ToolError("status can only be set to 'cancelled'.")
    if delivery_address:
        o["delivery_address"] = delivery_address.strip()
    if status:
        o["status"] = status
    return {"order_id": o["order_id"], "status": o["status"], "delivery_address": o["delivery_address"]}


def escalate_to_human(w: World, customer_id, reason, summary, order_id=None) -> dict:
    if not w.customer(customer_id):
        raise ToolError(f"Unknown customer_id {customer_id}.")
    allowed = ESCALATION_REASONS_V2 if "delivery_events" in w.data else ESCALATION_REASONS
    if reason not in allowed:
        raise ToolError(f"reason must be one of {allowed}.")
    esc = {"escalation_id": f"ESC-{700 + len(w.data['escalations'])}", "customer_id": customer_id,
           "order_id": (w.order(order_id) or {}).get("order_id", normalize_order_id(order_id)) if order_id else None, "reason": reason, "summary": summary,
           "created_at": w.data["now"]}
    w.data["escalations"].append(esc)
    return {"escalation_id": esc["escalation_id"], "follow_up": "within 24 hours"}


def get_delivery_events(w: World, order_id) -> dict:
    o = w.order(order_id)
    if not o or o["order_id"] not in w.data.get("delivery_events", {}):
        raise ToolError(f"No delivery events for {order_id}.")
    return {"order_id": o["order_id"], "promised_at": o["promised_at"], "events": w.data["delivery_events"][o["order_id"]]}


def get_payment(w: World, order_id) -> dict:
    o = w.order(order_id)
    if not o or o["order_id"] not in w.data.get("payments", {}):
        raise ToolError(f"No payment record for {order_id}.")
    return {"order_id": o["order_id"], **w.data["payments"][o["order_id"]], "subtotal": o["subtotal"],
            "support_refunds": o["refunds"]}


def get_ticket_history(w: World, customer_id) -> dict:
    if not w.customer(customer_id):
        raise ToolError(f"Unknown customer_id {customer_id}.")
    return {"customer_id": customer_id,
            "tickets": [t for t in w.data.get("tickets", []) if t["customer_id"] == customer_id]}


IMPL = {"get_delivery_events": get_delivery_events, "get_payment": get_payment, "get_ticket_history": get_ticket_history,
        "get_customer": get_customer, "verify_identity": verify_identity, "get_order": get_order,
        "issue_refund": issue_refund, "issue_credit": issue_credit, "update_order": update_order,
        "escalate_to_human": escalate_to_human}


def call_tool(w: World, name: str, args: dict) -> tuple[dict, bool]:
    """Run a tool and log it. Returns (result, is_error)."""
    entry = {"tool": name, "args": args, "verified_before": sorted(w.verified)}
    try:
        if name not in IMPL:
            raise ToolError(f"Unknown tool {name}.")
        result, err = copy.deepcopy(IMPL[name](w, **args)), False  # snapshot, not the live record
    except ToolError as e:
        result, err = {"error": str(e)}, True
    except TypeError as e:  # wrong or missing arguments
        result, err = {"error": f"Bad arguments: {e}"}, True
    entry.update(result=result, is_error=err)
    w.log.append(entry)
    return result, err
