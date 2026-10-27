"""Build world/v2/base.json for the harder v2 suite.

Adds what v1 lacks: a courier event log per order (the source of truth for
delivery), a payment record per order (promo discounts, automatic refunds for
items the restaurant marked unavailable), support-ticket history with earlier
promises, and Forkful Plus members with higher limits. Several orders are built
so that the order record disagrees with the event log. All people are invented.
Run: uv run python scripts/build_world_v2.py
"""
import json
from pathlib import Path

NOW = "2026-10-24T19:30:00-07:00"
T = lambda hm, day="2026-10-24": f"{day}T{hm}:00-07:00"  # noqa: E731
RESTAURANTS = {"R1": "Saffron Lane", "R2": "Pho Real", "R3": "Big Slice Pizza", "R4": "Green Bowl",
               "R5": "Taqueria Luz", "R6": "Burger Barn"}

# id, name, email, phone, address, plus member, refunds_last_30d
CUSTOMERS = [
    ("D201", "Aisha Rahman", "aisha.rahman@inbox.example", "+1 415-555-0231", "14 Grove St, Apt 3, Oakdale, CA 94601", True, 0),
    ("D202", "Leo Brandt", "leo.brandt@mailbox.example", "+1 415-555-0232", "870 Hill Rd, Oakdale, CA 94602", False, 0),
    ("D203", "Nina Kowalski", "nkowalski@post.example", "+1 415-555-0233", "5 Lake View Ct, Oakdale, CA 94603", False, 0),
    ("D204", "Carlos Mendes", "carlos.mendes@inbox.example", "+1 415-555-0234", "221 Second Ave, Oakdale, CA 94604", False, 1),
    ("D205", "Hana Sato", "hana.sato@mailbox.example", "+1 415-555-0235", "300 Tower Blvd, Apt 1204, Oakdale, CA 94605", False, 0),
    ("D206", "Owen Fitzgerald", "owen.fitz@post.example", "+1 415-555-0236", "47 Maple Dr, Oakdale, CA 94606", False, 0),
    ("D207", "Ruth Abara", "ruth.abara@inbox.example", "+1 415-555-0237", "19 Quarry Ln, Oakdale, CA 94607", False, 1),
    ("D208", "Victor Huang", "victor.huang@mailbox.example", "+1 415-555-0238", "63 Oak Terrace, Oakdale, CA 94608", False, 0),
    ("D209", "Isabel Duarte", "isabel.duarte@post.example", "+1 415-555-0239", "810 River Rd, Oakdale, CA 94609", True, 3),
    ("D210", "Sam Okafor", "sam.okafor@inbox.example", "+1 415-555-0240", "12 Pier St, Unit 5, Oakdale, CA 94610", False, 0),
    ("D211", "Fatima Zahra", "fatima.zahra@mailbox.example", "+1 415-555-0241", "400 Summit Ave, Oakdale, CA 94611", False, 0),
    ("D212", "Grant Holloway", "grant.holloway@post.example", "+1 415-555-0242", "77 Ridgecrest Dr, Oakdale, CA 94612", True, 0),
]
PLUS = {c[0] for c in CUSTOMERS if c[5]}
ORDERS, EVENTS, PAYMENTS = [], {}, {}


def order(oid, cust, rest, items, placed, promised, status, fee=2.99, tip=3.00, promo=None, address=None,
          record_delivered=None, events=(), auto_refunds=()):
    """items: (name, qty, unit_price, unavailable?)"""
    its = [{"item_id": f"{oid}-{i + 1}", "name": n, "qty": q, "unit_price": p} for i, (n, q, p, *_) in enumerate(items)]
    subtotal = round(sum(it["qty"] * it["unit_price"] for it in its), 2)
    fee = 0.0 if cust in PLUS else fee
    service = round(subtotal * 0.075, 2)
    discount = promo[1] if promo else 0.0
    total = round(subtotal - discount + fee + service + tip, 2)
    addr = address or next(c[4] for c in CUSTOMERS if c[0] == cust)
    picked = next((e["time"] for e in events if e["type"] == "picked_up"), None)
    ORDERS.append({"order_id": oid, "customer_id": cust, "restaurant_id": rest, "restaurant": RESTAURANTS[rest],
                   "items": its, "subtotal": subtotal, "promo_discount": discount, "delivery_fee": fee,
                   "service_fee": service, "tip": tip, "total": total, "status": status, "placed_at": placed,
                   "promised_at": promised, "picked_up_at": picked, "delivered_at": record_delivered,
                   "delivery_address": addr, "payment": {"method": "card", "brand": "Visa", "last4": "4242"},
                   "refunds": [], "credits": []})
    EVENTS[oid] = list(events)
    PAYMENTS[oid] = {"promo_code": promo[0] if promo else None, "promo_discount": discount, "charged": total,
                     "card": "Visa ending 4242", "automatic_refunds": list(auto_refunds)}


def ev(time, type_, **kw):
    return {"time": time, "type": type_, **kw}


# V01 Plus member: 50 min late (by handoff), samosas missing; a second order still preparing
order("Q-7101", "D201", "R1", [("Butter chicken", 1, 17.50), ("Chicken biryani", 1, 16.00), ("Samosas", 1, 6.50),
                               ("Garlic naan", 1, 4.50)], T("17:45"), T("18:30"), "delivered", record_delivered=T("19:20"),
      events=[ev(T("17:47"), "courier_assigned"), ev(T("18:55"), "picked_up"), ev(T("19:20"), "handoff", method="in_person")])
order("Q-7102", "D201", "R2", [("Beef pho", 1, 14.50), ("Iced coffee", 1, 4.75)], T("19:22"), T("20:10"), "preparing",
      events=[ev(T("19:23"), "courier_assigned")])
# V02 order record says on time; the event log shows a false "delivered" and a handoff 47 min late
order("Q-7201", "D202", "R6", [("Classic burger", 2, 12.00), ("Fries", 1, 4.00)], T("18:15"), T("19:00"), "delivered",
      fee=3.49, record_delivered=T("18:58"),
      events=[ev(T("18:16"), "courier_assigned"), ev(T("18:40"), "picked_up"),
              ev(T("18:58"), "marked_delivered", note="Courier app marked delivered 2.1 miles from the address"),
              ev(T("19:45"), "arrived"), ev(T("19:47"), "handoff", method="in_person")])
# V03 smoothie was unavailable and refunded automatically before delivery
order("Q-7301", "D203", "R4", [("Harvest bowl", 1, 13.50), ("Mango smoothie", 1, 6.75), ("Side salad", 1, 5.00)],
      T("17:55"), T("18:40"), "delivered", record_delivered=T("18:36"),
      events=[ev(T("18:12"), "item_unavailable", item="Mango smoothie", note="Restaurant marked unavailable"),
              ev(T("18:20"), "picked_up"), ev(T("18:36"), "handoff", method="in_person")],
      auto_refunds=[{"amount": 6.75, "item": "Mango smoothie", "time": T("18:13"),
                     "reason": "item unavailable; refunded automatically to card"}])
# V04 customer quotes last week's order number; tonight's order is the one with the missing elote
order("Q-7388", "D204", "R5", [("Carne asada tacos", 1, 13.00), ("Elote", 1, 5.50)], T("19:00", "2026-10-17"),
      T("19:45", "2026-10-17"), "delivered", record_delivered=T("19:38", "2026-10-17"),
      events=[ev(T("19:20", "2026-10-17"), "picked_up"), ev(T("19:38", "2026-10-17"), "handoff", method="in_person")])
order("Q-7401", "D204", "R5", [("Carne asada tacos", 1, 13.00), ("Elote", 1, 5.50), ("Agua fresca", 1, 3.75)],
      T("18:20"), T("19:05"), "delivered", record_delivered=T("19:01"),
      events=[ev(T("18:44"), "picked_up"), ev(T("19:01"), "handoff", method="in_person")])
# V05 left at the door with photo proof; customer says it never arrived
order("Q-7501", "D205", "R3", [("Large margherita pizza", 1, 21.00), ("Garlic knots", 1, 7.50), ("Caesar salad", 1, 9.50)],
      T("18:05"), T("18:50"), "delivered", record_delivered=T("19:02"),
      events=[ev(T("18:35"), "picked_up"), ev(T("19:02"), "handoff", method="left_at_door",
                                                proof="photo PH-55120: bag at door of apartment 1204")])
# V06 promo order, one of two phos missing
order("Q-7601", "D206", "R2", [("Beef pho", 2, 15.00), ("Spring rolls", 1, 7.00), ("Banh mi", 1, 13.00)],
      T("18:00"), T("18:45"), "delivered", promo=("WELCOME10", 10.00), record_delivered=T("18:41"),
      events=[ev(T("18:22"), "picked_up"), ev(T("18:41"), "handoff", method="in_person")])
# V07 yesterday's order: an agent promised credit that was never issued
order("Q-7690", "D207", "R3", [("Large pepperoni pizza", 1, 21.00), ("Garlic knots", 1, 6.50)],
      T("19:10", "2026-10-23"), T("19:55", "2026-10-23"), "delivered", record_delivered=T("19:49", "2026-10-23"),
      events=[ev(T("19:31", "2026-10-23"), "picked_up"), ev(T("19:49", "2026-10-23"), "handoff", method="in_person")])
# V08 late 30 min, already compensated in an earlier chat today
order("Q-7801", "D208", "R5", [("Chicken burrito", 1, 11.50), ("Chips and salsa", 1, 4.50)], T("17:30"), T("18:15"),
      "delivered", record_delivered=T("18:45"),
      events=[ev(T("18:25"), "picked_up"), ev(T("18:45"), "handoff", method="in_person")])
# V09 Plus member with 3 refunds in 30 days; wrong item, got sick (food safety)
order("Q-7901", "D209", "R1", [("Paneer tikka masala", 1, 15.50), ("Jeera rice", 1, 4.25)], T("18:10"), T("18:55"),
      "delivered", record_delivered=T("18:50"),
      events=[ev(T("18:33"), "picked_up"), ev(T("18:50"), "handoff", method="in_person")])
# V10 failed delivery: customer unreachable, food returned
order("Q-8001", "D210", "R6", [("Bacon cheeseburger", 1, 14.50), ("Onion rings", 1, 6.00)], T("18:20"), T("19:05"),
      "delivery_failed",
      events=[ev(T("18:47"), "picked_up"), ev(T("19:05"), "arrived"),
              ev(T("19:06"), "call_attempt", result="no answer"), ev(T("19:09"), "call_attempt", result="no answer"),
              ev(T("19:15"), "delivery_failed", reason="customer_unreachable"),
              ev(T("19:28"), "returned_to_restaurant")])
# V11 order record still says preparing, but the courier picked it up
order("Q-8101", "D211", "R4", [("Harvest bowl", 2, 13.50), ("Lemonade", 2, 4.00)], T("18:50"), T("19:40"), "preparing",
      events=[ev(T("18:51"), "courier_assigned"), ev(T("19:27"), "picked_up")])
# V12 Plus member, whole order never delivered (courier dropped out); record wrongly says delivered
order("Q-8201", "D212", "R3", [("Large pepperoni pizza", 2, 21.00), ("Large veggie pizza", 1, 22.00),
                               ("Garlic knots", 1, 7.50), ("2L soda", 1, 2.50)], T("17:40"), T("18:30"), "delivered",
      tip=8.00, record_delivered=T("18:52"),
      events=[ev(T("18:05"), "picked_up"), ev(T("18:40"), "courier_unassigned", note="courier reported vehicle breakdown"),
              ev(T("18:52"), "marked_delivered", note="automatic status update; no handoff recorded")])

TICKETS = [
    {"ticket_id": "TK-881", "customer_id": "D207", "created_at": T("20:15", "2026-10-23"), "order_id": "Q-7690",
     "summary": "Garlic knots missing from order.", "agent_actions": [],
     "promises": [{"text": "Agent promised $6.50 account credit for the missing garlic knots, to be applied within 24 hours.",
                   "amount": 6.50, "type": "credit"}]},
    {"ticket_id": "TK-902", "customer_id": "D208", "created_at": T("19:05"), "order_id": "Q-7801",
     "summary": "Order arrived 30 minutes late.",
     "agent_actions": ["Issued $2.99 account credit (delivery fee) for late delivery."], "promises": []},
    {"ticket_id": "TK-640", "customer_id": "D209", "created_at": T("12:30", "2026-10-11"), "order_id": None,
     "summary": "Missing item; refunded.", "agent_actions": ["Refund issued."], "promises": []},
]
PRIOR_CREDITS = {"D208": [{"amount": 2.99, "reason": "late_delivery", "order_id": "Q-7801", "item_ids": [],
                           "created_at": T("19:07")}]}


def main() -> None:
    customers = []
    for c in CUSTOMERS:
        ledger = PRIOR_CREDITS.get(c[0], [])
        customers.append({"customer_id": c[0], "name": c[1], "email": c[2], "phone": c[3], "default_address": c[4],
                          "plus_member": c[5], "refunds_last_30d": c[6],
                          "credit_balance": round(sum(e["amount"] for e in ledger), 2), "credit_ledger": ledger})
    for o in ORDERS:
        o["credits"] = [e for c in customers for e in c["credit_ledger"] if e["order_id"] == o["order_id"]]
    world = {"now": NOW, "restaurants": [{"restaurant_id": k, "name": v} for k, v in RESTAURANTS.items()],
             "customers": customers, "orders": ORDERS, "delivery_events": EVENTS, "payments": PAYMENTS,
             "tickets": TICKETS, "escalations": []}
    out = Path(__file__).resolve().parents[1] / "world" / "v2" / "base.json"
    out.write_text(json.dumps(world, indent=1) + "\n")
    print(f"wrote {out}")
    for o in ORDERS:
        print(o["order_id"], o["customer_id"], o["status"], "sub", o["subtotal"], "promo", o["promo_discount"],
              "fee", o["delivery_fee"], "svc", o["service_fee"], "tip", o["tip"], "total", o["total"])


if __name__ == "__main__":
    main()
