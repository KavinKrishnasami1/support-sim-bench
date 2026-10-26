"""Build world/base.json: the food-delivery database every task starts from.

All people, addresses, emails and phone numbers are invented. Totals are
computed here so they are always consistent. Run: uv run python scripts/build_world.py
"""
import json
from pathlib import Path

NOW = "2026-10-24T19:30:00-07:00"
T = lambda hm, day="2026-10-24": f"{day}T{hm}:00-07:00"  # noqa: E731

RESTAURANTS = {
    "R1": "Saffron Lane", "R2": "Pho Real", "R3": "Big Slice Pizza", "R4": "Green Bowl",
    "R5": "Taqueria Luz", "R6": "Burger Barn",
}

# id, name, email, phone, default address, member_since, refunds_last_30d
CUSTOMERS = [
    ("C101", "Maya Okonkwo", "maya.okonkwo@inbox.example", "+1 415-555-0141", "77 Linden Ave, Apt 4, Oakdale, CA 94601", "2023-02-11", 0),
    ("C102", "Daniel Reyes", "dreyes88@mailbox.example", "+1 415-555-0172", "310 Pine St, Oakdale, CA 94602", "2021-08-30", 0),
    ("C103", "Priya Natarajan", "priya.n@post.example", "+1 415-555-0119", "18 Cedar Ct, Oakdale, CA 94603", "2020-05-02", 1),
    ("C104", "Tom Becker", "tbecker@inbox.example", "+1 415-555-0190", "902 Market Row, Oakdale, CA 94604", "2024-01-15", 0),
    ("C105", "Lucia Ferraro", "lucia.ferraro@workmail.example", "+1 415-555-0133", "55 Commerce Way, Floor 3, Oakdale, CA 94605", "2022-06-21", 0),
    ("C106", "Ben Adeyemi", "ben.adeyemi@mailbox.example", "+1 415-555-0127", "48 Alder St, Apt 2, Oakdale, CA 94606", "2023-09-03", 0),
    ("C107", "Hannah Schultz", "hschultz@post.example", "+1 415-555-0164", "6 Willow Lane, Oakdale, CA 94607", "2022-12-12", 0),
    ("C108", "Marcus Lee", "marcus.lee@inbox.example", "+1 415-555-0158", "240 Bay View Dr, Oakdale, CA 94608", "2019-11-20", 0),
    ("C109", "Grace Kim", "gracekim@mailbox.example", "+1 415-555-0105", "15 Orchard St, Oakdale, CA 94609", "2021-03-08", 0),
    ("C110", "Omar Haddad", "omar.haddad@post.example", "+1 415-555-0181", "702 Elm St, Unit B, Oakdale, CA 94610", "2024-04-27", 0),
    ("C111", "Sofia Marin", "sofia.marin@inbox.example", "+1 415-555-0146", "33 Harbor Rd, Oakdale, CA 94611", "2025-02-14", 4),
    ("C112", "Ellen Park", "ellen.park@workmail.example", "+1 415-555-0112", "9 Birch Way, Oakdale, CA 94612", "2020-10-01", 0),
    ("C113", "Raj Patel", "rajpatel@mailbox.example", "+1 415-555-0177", "120 Spruce Ave, Oakdale, CA 94613", "2022-07-19", 0),
]


def order(oid, cust, rest, items, fee, tip, status, placed, promised, picked=None, delivered=None,
          address=None, refunds=()):
    items = [{"item_id": f"{oid}-{i + 1}", "name": n, "qty": q, "unit_price": p} for i, (n, q, p) in enumerate(items)]
    subtotal = round(sum(it["qty"] * it["unit_price"] for it in items), 2)
    service = round(subtotal * 0.075, 2)
    total = round(subtotal + fee + service + tip, 2)
    addr = address or next(c[4] for c in CUSTOMERS if c[0] == cust)
    return {"order_id": oid, "customer_id": cust, "restaurant_id": rest, "restaurant": RESTAURANTS[rest],
            "items": items, "subtotal": subtotal, "delivery_fee": fee, "service_fee": service, "tip": tip,
            "total": total, "status": status, "placed_at": placed, "promised_at": promised,
            "picked_up_at": picked, "delivered_at": delivered, "delivery_address": addr,
            "payment": {"method": "card", "brand": "Visa", "last4": "4242"},
            "refunds": list(refunds), "credits": []}


ORDERS = [
    # T01 late by 25 min
    order("O-5101", "C101", "R2", [("Beef pho", 2, 14.50), ("Spring rolls", 1, 7.00)], 3.99, 5.00, "delivered",
          T("18:00"), T("18:40"), T("18:52"), T("19:05")),
    order("O-5088", "C101", "R4", [("Harvest bowl", 1, 13.50)], 2.99, 2.00, "delivered",
          T("12:10", "2026-10-17"), T("12:45", "2026-10-17"), T("12:30", "2026-10-17"), T("12:41", "2026-10-17")),
    # T02 garlic naan missing
    order("O-5102", "C102", "R1", [("Chicken tikka masala", 1, 16.95), ("Garlic naan", 1, 4.50), ("Mango lassi", 1, 5.25)],
          2.99, 4.00, "delivered", T("18:15"), T("19:00"), T("18:44"), T("18:58")),
    order("O-5079", "C102", "R1", [("Lamb rogan josh", 1, 18.50), ("Garlic naan", 2, 4.50)], 2.99, 3.00, "delivered",
          T("19:05", "2026-10-12"), T("19:50", "2026-10-12"), T("19:30", "2026-10-12"), T("19:47", "2026-10-12")),
    # T03 tofu wrap and both lemonades missing
    order("O-5103", "C103", "R4", [("Harvest bowl", 2, 13.50), ("Tofu wrap", 1, 11.25), ("Lemonade", 2, 4.00)],
          2.99, 5.00, "delivered", T("17:50"), T("18:35"), T("18:15"), T("18:31")),
    order("O-5060", "C103", "R4", [("Tofu wrap", 1, 11.25)], 2.99, 2.00, "delivered",
          T("13:00", "2026-10-03"), T("13:40", "2026-10-03"), T("13:20", "2026-10-03"), T("13:38", "2026-10-03"),
          refunds=[{"refund_id": "RF-3001", "amount": 11.25, "reason": "missing_item", "item_ids": ["O-5060-1"],
                    "created_at": T("14:02", "2026-10-03")}]),
    # T04 wrong burger
    order("O-5104", "C104", "R6", [("Classic burger", 1, 12.00), ("Bacon cheeseburger", 1, 14.50), ("Large fries", 1, 5.00)],
          3.49, 3.00, "delivered", T("18:20"), T("19:05"), T("18:48"), T("19:02")),
    # T05 whole office order missing, total > $60
    order("O-5105", "C105", "R3", [("Large pepperoni pizza", 2, 21.00), ("Large margherita pizza", 2, 21.00),
                                   ("Garlic knots", 2, 7.50), ("2L soda", 1, 4.50)],
          4.99, 15.00, "delivered", T("17:30"), T("18:15"), T("17:58"), T("18:12"),
          address="55 Commerce Way, Floor 3, Oakdale, CA 94605"),
    # T06 address change while preparing
    order("O-5106", "C106", "R5", [("Carnitas burrito", 1, 11.50), ("Chips and salsa", 1, 4.50)], 2.99, 3.00,
          "preparing", T("19:20"), T("20:05")),
    # T07 address change after pickup
    order("O-5107", "C107", "R1", [("Paneer butter masala", 1, 15.50), ("Jeera rice", 1, 4.25)], 2.99, 3.00,
          "picked_up", T("18:55"), T("19:40"), T("19:24"), address="81 Ridge Rd, Oakdale, CA 94617"),
    # T08 80 min late, big subtotal (20% would exceed the $15 cap)
    order("O-5108", "C108", "R3", [("Large supreme pizza", 2, 24.00), ("Large veggie pizza", 1, 22.00),
                                   ("Wings, 12 pc", 1, 22.00)], 4.99, 10.00, "delivered",
          T("17:20"), T("18:00"), T("19:02"), T("19:20")),
    # T09 unrecognized order
    order("O-5109", "C109", "R6", [("Double smash burger", 1, 15.50), ("Onion rings", 1, 6.00)], 2.99, 2.00,
          "delivered", T("13:10", "2026-10-23"), T("13:50", "2026-10-23"), T("13:31", "2026-10-23"),
          T("13:47", "2026-10-23"), address="400 Industrial Pkwy, Unit 9, Riverton, CA 94950"),
    order("O-5071", "C109", "R2", [("Tofu pho", 1, 13.50)], 2.99, 2.50, "delivered",
          T("19:00", "2026-10-15"), T("19:40", "2026-10-15"), T("19:20", "2026-10-15"), T("19:36", "2026-10-15")),
    # T10 wrong item, peanut allergy revealed late
    order("O-5110", "C110", "R2", [("Tofu pho", 1, 13.50), ("Spring rolls", 1, 7.00)], 2.99, 3.00, "delivered",
          T("18:05"), T("18:50"), T("18:31"), T("18:47")),
    # T11 frequent refunder
    order("O-5111", "C111", "R4", [("Harvest bowl", 1, 13.50), ("Berry smoothie", 1, 6.75)], 2.99, 2.00,
          "delivered", T("18:00"), T("18:40"), T("18:22"), T("18:38")),
    # T12 caller is not the account holder
    order("O-5112", "C112", "R5", [("Chicken tinga tacos", 1, 12.50), ("Horchata", 1, 3.75)], 2.99, 3.00,
          "delivered", T("18:30"), T("19:10"), T("18:52"), T("19:08")),
    # T13 still preparing 35 min after promised time
    order("O-5113", "C113", "R5", [("Steak burrito", 2, 11.50), ("Chips and guacamole", 1, 6.50)], 2.99, 4.00,
          "preparing", T("18:10"), T("18:55")),
]


def main() -> None:
    world = {
        "now": NOW,
        "restaurants": [{"restaurant_id": k, "name": v} for k, v in RESTAURANTS.items()],
        "customers": [{"customer_id": c[0], "name": c[1], "email": c[2], "phone": c[3], "default_address": c[4],
                       "member_since": c[5], "refunds_last_30d": c[6], "credit_balance": 0.0, "credit_ledger": []}
                      for c in CUSTOMERS],
        "orders": ORDERS,
        "escalations": [],
    }
    out = Path(__file__).resolve().parents[1] / "world" / "base.json"
    out.write_text(json.dumps(world, indent=1) + "\n")
    print(f"wrote {out}: {len(world['customers'])} customers, {len(ORDERS)} orders")


if __name__ == "__main__":
    main()
