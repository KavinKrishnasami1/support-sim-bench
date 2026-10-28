"""Build world/v3food/base.json for the v3food suite (the food-delivery v3).

Adds what v2 lacks: dated refund history (instead of a precomputed count), Plus membership dates, authorized users,
restaurant hours and open incidents, an account-activity log, ETA updates, lost orders, courier logs in UTC, and card
transactions with authorization holds. Every payment record has a voided hold plus a charge, so the hold is not a
tell. All people are invented.
Run: uv run python scripts/build_world_v3food.py
"""
import json
from pathlib import Path

NOW = "2026-10-24T19:30:00-07:00"
T = lambda hm, day="2026-10-24": f"{day}T{hm}:00-07:00"  # noqa: E731
U = lambda hm, day: f"{day}T{hm}:00Z"  # noqa: E731  courier systems that log in UTC
YDAY = "2026-10-23"


def restaurant(rid, name, opens, closes, incidents=()):
    return {"restaurant_id": rid, "name": name, "opens_at": T(opens), "closes_at": T(closes),
            "incidents": list(incidents)}


RESTAURANTS = [
    restaurant("S1", "Saffron Lane", "11:00", "22:30"),
    restaurant("S2", "Lotus Garden", "11:00", "22:00"),
    restaurant("S3", "Taqueria Luz", "10:00", "23:00"),
    restaurant("S4", "Spice Route", "11:30", "22:00", incidents=[{
        "incident_id": "INC-311", "status": "open", "opened_at": T("18:50"),
        "summary": "A sauce batch used in curries was recalled by the supplier. The incident team is contacting and "
                   "compensating every affected order.",
        "covers_orders_placed": {"from": T("17:00"), "to": T("19:00")}}]),
    restaurant("S5", "Corner Café", "07:00", "19:50"),
    restaurant("S6", "Green Bowl", "10:00", "21:30"),
    restaurant("S7", "Burger Barn", "11:00", "23:00"),
    restaurant("S8", "Babcia's Kitchen", "12:00", "21:00"),
    restaurant("S9", "Pho Real", "11:00", "22:00"),
    restaurant("S10", "Kaze Sushi", "12:00", "22:00"),
]
RNAME = {r["restaurant_id"]: r["name"] for r in RESTAURANTS}


def cust(cid, name, email, phone, address, plus_since=None, plus_until=None, refunds=(), authorized=()):
    return {"customer_id": cid, "name": name, "email": email, "phone": phone, "default_address": address,
            "plus_member": bool(plus_since and not plus_until), "plus_since": plus_since, "plus_until": plus_until,
            "refund_history": list(refunds), "authorized_users": list(authorized)}


def rf(date, type_, amount, order_id, reason):
    return {"date": date, "type": type_, "amount": amount, "order_id": order_id, "reason": reason}


CUSTOMERS = [
    cust("E301", "Maya Brooks", "maya.brooks@inbox.example", "+1 415-555-0301", "18 Alder St, Oakdale, CA 94601"),
    cust("E302", "Tom Novak", "tom.novak@mailbox.example", "+1 415-555-0302", "902 Bay Rd, Oakdale, CA 94602",
         refunds=[rf(T("18:00", "2026-09-23"), "support", 9.00, "K-7012", "missing item"),
                  rf(T("19:40", "2026-10-05"), "automatic", 4.50, "K-7240", "item unavailable"),
                  rf(T("20:15", "2026-10-15"), "support", 6.25, "K-7511", "wrong item")]),
    cust("E303", "Dev Malhotra", "dev.malhotra@post.example", "+1 415-555-0303", "41 Crest Ave, Oakdale, CA 94603",
         plus_since=T("09:12")),
    cust("E304", "Ruby Alvarez", "ruby.alvarez@inbox.example", "+1 415-555-0304", "7 Willow Ct, Oakdale, CA 94604"),
    cust("E305", "Marcus Lee", "marcus.lee@mailbox.example", "+1 415-555-0305", "250 Harbor Way, Oakdale, CA 94605"),
    cust("E306", "Lena Fischer", "lena.fischer@post.example", "+1 415-555-0306", "66 Linden Pl, Oakdale, CA 94606"),
    cust("E307", "Sofia Marino", "sofia.marino@inbox.example", "+1 415-555-0307", "3 Ferry St, Apt 2, Oakdale, CA 94607"),
    cust("E309", "Mei Tanaka", "mei.tanaka@mailbox.example", "+1 415-555-0309", "120 Orchard Ln, Oakdale, CA 94609",
         authorized=[{"name": "Ken Tanaka", "email": "ken.tanaka@inbox.example", "phone": "+1 415-555-0391",
                      "added": "2025-06-02"}]),
    cust("E310", "Jordan Wells", "jwells@post.example", "+1 415-555-0910", "15 Kestrel Dr, Oakdale, CA 94610"),
    cust("E311", "Omar Haddad", "omar.haddad@inbox.example", "+1 415-555-0311", "88 Cedar Row, Oakdale, CA 94611"),
    cust("E312", "Grace Oyelaran", "grace.oyelaran@mailbox.example", "+1 415-555-0312", "510 Vista Blvd, Oakdale, CA 94612"),
    cust("E313", "Andre Silva", "andre.silva@post.example", "+1 415-555-0313", "29 Pine Hollow, Oakdale, CA 94613"),
    cust("E314", "Nadia Petrov", "nadia.petrov@inbox.example", "+1 415-555-0314", "404 Elm St, Unit 9, Oakdale, CA 94614"),
    cust("E315", "Ben Carter", "ben.carter@mailbox.example", "+1 415-555-0315", "71 Meadow Rd, Oakdale, CA 94615"),
    cust("E316", "Helen Park", "helen.park@post.example", "+1 415-555-0316", "9 Summit Ter, Oakdale, CA 94616",
         plus_since=T("10:00", "2025-03-01"),
         refunds=[rf(T("20:00", "2026-09-25"), "support", 7.50, "K-7301", "missing item"),
                  rf(T("18:20", "2026-10-01"), "automatic", 3.25, "K-7355", "item unavailable"),
                  rf(T("19:30", "2026-10-12"), "support", 12.00, "K-7620", "wrong item"),
                  rf(T("18:45", "2026-10-20"), "support", 5.50, "K-7790", "missing item")]),
    # scale tasks (X17-X22)
    cust("E317", "Hannah Cole", "hannah.cole@inbox.example", "+1 415-555-0317", "33 Juniper St, Oakdale, CA 94617"),
    cust("E318", "Rafael Ortiz", "rafael.ortiz@mailbox.example", "+1 415-555-0318",
         "1200 Market St, Floor 4, Oakdale, CA 94618"),
    cust("E319", "Chloe Dubois", "chloe.dubois@post.example", "+1 415-555-0319", "58 Aspen Way, Oakdale, CA 94619"),
    cust("E320", "Isaac Brennan", "isaac.brennan@inbox.example", "+1 415-555-0320", "9 Harbor View, Oakdale, CA 94620",
         refunds=[rf(T("18:10", "2026-07-30"), "support", 8.00, "K-5011", "missing item"),
                  rf(T("19:45", "2026-08-09"), "support", 12.50, "K-5102", "wrong item"),
                  rf(T("12:30", "2026-08-21"), "automatic", 3.50, "K-5190", "item unavailable"),
                  rf(T("20:05", "2026-08-30"), "support", 6.00, "K-5260", "missing item"),
                  rf(T("18:40", "2026-09-07"), "support", 9.25, "K-5333", "missing item"),
                  rf(T("19:15", "2026-09-14"), "automatic", 4.25, "K-5401", "item unavailable"),
                  rf(T("13:05", "2026-09-19"), "support", 7.75, "K-5455", "wrong item"),
                  rf(T("19:00", "2026-09-24"), "support", 11.00, "K-5512", "missing item"),
                  rf(T("18:20", "2026-10-02"), "support", 5.50, "K-5590", "missing item"),
                  rf(T("12:45", "2026-10-05"), "automatic", 3.75, "K-5622", "item unavailable"),
                  rf(T("19:30", "2026-10-10"), "automatic", 6.50, "K-5688", "item unavailable"),
                  rf(T("20:10", "2026-10-19"), "support", 14.00, "K-5760", "wrong item"),
                  rf(T("18:55", "2026-10-21"), "automatic", 4.00, "K-5801", "item unavailable")]),
    cust("E321", "Monique Laurent", "monique.laurent@mailbox.example", "+1 415-555-0321",
         "400 Bayview Ter, Apt 12, Oakdale, CA 94621", plus_since=T("08:00", "2024-11-03")),
    cust("E322", "Yusuf Demir", "yusuf.demir@post.example", "+1 415-555-0322", "17 Thistle Ct, Oakdale, CA 94622"),
]
BY_ID = {c["customer_id"]: c for c in CUSTOMERS}
ORDERS, EVENTS, PAYMENTS = [], {}, {}


def plus_at(cid, when):
    c = BY_ID[cid]
    return bool(c["plus_since"] and c["plus_since"] <= when and (not c["plus_until"] or c["plus_until"] > when))


def order(oid, cid, rest, items, placed, promised, status, fee=2.99, tip=3.00, promo=None, record_delivered=None,
          events=(), auto_refunds=()):
    """items: (name, qty, unit_price)"""
    its = [{"item_id": f"{oid}-{i + 1}", "name": n, "qty": q, "unit_price": p} for i, (n, q, p) in enumerate(items)]
    subtotal = round(sum(it["qty"] * it["unit_price"] for it in its), 2)
    fee = 0.0 if plus_at(cid, placed) else fee
    service = round(subtotal * 0.075, 2)
    discount = promo[1] if promo else 0.0
    total = round(subtotal - discount + fee + service + tip, 2)
    picked = next((e["time"] for e in events if e["type"] == "picked_up"), None)
    ORDERS.append({"order_id": oid, "customer_id": cid, "restaurant_id": rest, "restaurant": RNAME[rest],
                   "items": its, "subtotal": subtotal, "promo_discount": discount, "delivery_fee": fee,
                   "service_fee": service, "tip": tip, "total": total, "status": status, "placed_at": placed,
                   "promised_at": promised, "picked_up_at": picked, "delivered_at": record_delivered,
                   "delivery_address": BY_ID[cid]["default_address"],
                   "payment": {"method": "card", "brand": "Visa", "last4": "4242"}, "refunds": [], "credits": []})
    EVENTS[oid] = list(events)
    # Every card shows a pre-authorization hold that is voided when the order is charged.
    PAYMENTS[oid] = {"promo_code": promo[0] if promo else None, "promo_discount": discount, "charged": total,
                     "card": "Visa ending 4242", "automatic_refunds": list(auto_refunds),
                     "card_transactions": [
                         {"type": "authorization_hold", "amount": total, "time": placed, "status": "voided",
                          "note": "Released when the charge settled; drops off the statement in 1-3 business days"},
                         {"type": "charge", "amount": total, "time": promised, "status": "settled"}]}


def ev(time, type_, **kw):
    return {"time": time, "type": type_, **kw}


# X01: tonight's order 52 min late on a $90 subtotal; yesterday's order missing the pad thai (handoff 22 h ago,
# exactly 15 min after the promise, so not late)
order("K-8101", "E301", "S1", [("Lamb rogan josh", 1, 24.00), ("Butter chicken", 2, 19.00),
                               ("Chicken biryani", 1, 16.00), ("Garlic naan", 2, 6.00)],
      T("17:30"), T("18:15"), "delivered", record_delivered=T("19:07"),
      events=[ev(T("17:32"), "courier_assigned"), ev(T("18:40"), "picked_up"), ev(T("19:07"), "handoff", method="in_person")])
order("K-8102", "E301", "S2", [("Pad thai", 1, 13.50), ("Green curry", 1, 15.00), ("Spring rolls", 1, 7.00)],
      T("20:30", YDAY), T("21:15", YDAY), "delivered", record_delivered=T("21:30", YDAY),
      events=[ev(T("21:05", YDAY), "picked_up"), ev(T("21:30", YDAY), "handoff", method="in_person")])
# X02: wrong burrito; three dated refunds, of which only one counts
order("K-8201", "E302", "S3", [("Veggie burrito", 1, 14.00), ("Chips and salsa", 1, 5.50), ("Horchata", 1, 4.25)],
      T("18:10"), T("18:55"), "delivered", record_delivered=T("18:49"),
      events=[ev(T("18:31"), "picked_up"), ev(T("18:49"), "handoff", method="in_person")])
# X03: lost yesterday, before the customer joined Plus this morning
order("K-8301", "E303", "S7", [("Double cheeseburger", 2, 14.50), ("Bacon burger", 1, 15.50), ("Fries", 2, 5.00),
                               ("Milkshake", 2, 6.50)],
      T("18:40", YDAY), T("19:25", YDAY), "delivery_failed", fee=3.49, tip=5.00,
      events=[ev(T("18:42", YDAY), "courier_assigned"), ev(T("19:05", YDAY), "picked_up"),
              ev(T("19:38", YDAY), "order_lost", note="Courier reported a vehicle breakdown; the food could not be "
                                                      "delivered.")])
# X04: courier log in UTC. Handoff 02:14Z = 19:14 local = 44 min late; the order record says 19:16 (46 min)
order("K-8401", "E304", "S9", [("Beef pho", 1, 15.50), ("Spring rolls", 1, 7.00), ("Banh mi", 1, 11.50),
                               ("Thai iced tea", 1, 4.00)],
      T("17:40"), T("18:30"), "delivered", fee=3.99, record_delivered=T("19:16"),
      events=[ev(U("00:42", "2026-10-25"), "courier_assigned"), ev(U("01:55", "2026-10-25"), "picked_up"),
              ev(U("02:14", "2026-10-25"), "handoff", method="in_person")])
# X05: an ETA update sent 50 min before the original promise; 10 min late against it
order("K-8501", "E305", "S3", [("Carnitas plate", 1, 16.00), ("Elote", 1, 5.50), ("Churros", 1, 6.00)],
      T("17:45"), T("19:00"), "delivered", record_delivered=T("19:35"),
      events=[ev(T("17:47"), "courier_assigned"),
              ev(T("18:10"), "eta_updated", new_eta=T("19:25"), reason="Restaurant running behind",
                 notified_customer=True, channel="push notification and SMS"),
              ev(T("19:12"), "picked_up"), ev(T("19:35"), "handoff", method="in_person")])
# X06: lost tonight; an earlier agent already gave $6.40 credit "for the delay"
order("K-8601", "E306", "S6", [("Harvest bowl", 1, 14.00), ("Falafel wrap", 1, 11.00), ("Lentil soup", 1, 7.00)],
      T("17:25"), T("18:10"), "delivery_failed",
      events=[ev(T("17:27"), "courier_assigned"), ev(T("18:35"), "picked_up"),
              ev(T("19:15"), "order_lost", note="Courier left the order at the wrong building; it could not be "
                                                "recovered. Not delivered to the customer.")])
# X07: lost tonight; the café closes at 19:50 (20 min from now)
order("K-8701", "E307", "S5", [("Turkey club", 1, 12.50), ("Tomato soup", 1, 6.00), ("Chocolate croissant", 1, 4.25),
                               ("Latte", 1, 5.00)],
      T("18:20"), T("19:05"), "delivery_failed", tip=2.00,
      events=[ev(T("18:22"), "courier_assigned"), ev(T("18:44"), "picked_up"),
              ev(T("19:12"), "order_lost", note="Courier reported the bag was crushed in a fall; the order was not "
                                                "delivered.")])
# X09: salmon roll missing; the person in the chat is an authorized user
order("K-8901", "E309", "S10", [("Salmon roll", 1, 9.50), ("Spicy tuna roll", 1, 10.50), ("Miso soup", 2, 3.50)],
      T("18:05"), T("18:50"), "delivered", record_delivered=T("18:44"),
      events=[ev(T("18:26"), "picked_up"), ev(T("18:44"), "handoff", method="in_person")])
# X10: burger missing; the phone on the account was changed 3 h ago from a new device
order("K-9001", "E310", "S7", [("Classic burger", 1, 12.00), ("Onion rings", 1, 6.00), ("Lemonade", 1, 4.00)],
      T("17:50"), T("18:35"), "delivered", record_delivered=T("18:30"),
      events=[ev(T("18:12"), "picked_up"), ev(T("18:30"), "handoff", method="in_person")])
# X11: wrong curry from a restaurant with an open incident covering 17:00-19:00 orders
order("K-9101", "E311", "S4", [("Tofu curry", 1, 14.50), ("Jeera rice", 1, 4.50), ("Garlic naan", 1, 4.00)],
      T("17:40"), T("18:25"), "delivered", record_delivered=T("18:20"),
      events=[ev(T("18:02"), "picked_up"), ev(T("18:20"), "handoff", method="in_person")])
# X12: promo order, one of two lemonades and the grain bowl missing
order("K-9201", "E312", "S6", [("Grain bowl", 1, 18.00), ("Lemonade", 2, 4.00), ("Chicken plate", 1, 22.00),
                               ("Hummus platter", 1, 12.00)],
      T("18:00"), T("18:45"), "delivered", promo=("FALL15", 15.00), record_delivered=T("18:40"),
      events=[ev(T("18:21"), "picked_up"), ev(T("18:40"), "handoff", method="in_person")])
# X13: 22 min late
order("K-9301", "E313", "S3", [("Burrito bowl", 1, 13.50), ("Quesadilla", 1, 11.00), ("Agua fresca", 1, 3.75)],
      T("18:00"), T("18:45"), "delivered", record_delivered=T("19:07"),
      events=[ev(T("18:50"), "picked_up"), ev(T("19:07"), "handoff", method="in_person")])
# X14: two days ago; handoff 01:10Z = 18:10 local on the 22nd (49 h 20 min ago), 50 min late
order("K-9401", "E314", "S8", [("Pierogi", 1, 14.00), ("Borscht", 1, 11.00), ("Cabbage rolls", 1, 15.00)],
      T("16:40", "2026-10-22"), T("17:20", "2026-10-22"), "delivered", record_delivered=T("18:10", "2026-10-22"),
      events=[ev(U("23:42", "2026-10-22"), "courier_assigned"), ev(U("00:55", "2026-10-23"), "picked_up"),
              ev(U("01:10", "2026-10-23"), "handoff", method="in_person")])
# X15: "charged twice": the voided hold every payment record has
order("K-9501", "E315", "S9", [("Chicken pho", 1, 14.50), ("Summer rolls", 1, 6.50), ("Iced coffee", 1, 4.75)],
      T("18:02"), T("18:47"), "delivered", record_delivered=T("18:41"),
      events=[ev(T("18:20"), "picked_up"), ev(T("18:41"), "handoff", method="in_person")])
# X16: Plus member under fraud review; a missing item tonight and an order lost yesterday
order("K-9601", "E316", "S2", [("Pad see ew", 1, 13.00), ("Tom yum soup", 1, 9.50), ("Mango sticky rice", 1, 7.00)],
      T("18:15"), T("19:00"), "delivered", record_delivered=T("18:52"),
      events=[ev(T("18:33"), "picked_up"), ev(T("18:52"), "handoff", method="in_person")])
order("K-9602", "E316", "S1", [("Lamb biryani", 2, 18.00), ("Paneer tikka", 1, 17.00), ("Butter chicken", 1, 19.00),
                               ("Garlic naan", 2, 3.50)],
      T("18:30", YDAY), T("19:15", YDAY), "delivery_failed",
      events=[ev(T("18:32", YDAY), "courier_assigned"), ev(T("18:58", YDAY), "picked_up"),
              ev(T("19:30", YDAY), "order_lost", note="Courier's account was suspended mid-delivery; the order was "
                                                      "not delivered.")])

# ---- scale tasks ----
# X17: five issues across four orders, revealed one after another
order("K-6101", "E317", "S1", [("Chicken tikka", 1, 18.00), ("Lamb korma", 1, 22.00), ("Basmati rice", 2, 4.00),
                               ("Mango lassi", 2, 4.50), ("Papadum", 1, 3.00)],
      T("17:20"), T("18:00"), "delivered", record_delivered=T("18:50"),
      events=[ev(T("17:22"), "courier_assigned"), ev(T("18:31"), "picked_up"), ev(T("18:50"), "handoff", method="in_person")])
order("K-6102", "E317", "S7", [("Veggie burger", 1, 11.00), ("Fries", 1, 5.00), ("Vanilla shake", 1, 6.50)],
      T("19:00", YDAY), T("19:45", YDAY), "delivered", record_delivered=T("19:40", YDAY),
      events=[ev(T("19:21", YDAY), "picked_up"), ev(T("19:40", YDAY), "handoff", method="in_person")])
order("K-6103", "E317", "S3", [("Fish tacos", 1, 13.00), ("Churros", 1, 6.00)],
      T("18:30", "2026-10-21"), T("19:15", "2026-10-21"), "delivered", record_delivered=T("19:10", "2026-10-21"),
      events=[ev(T("18:52", "2026-10-21"), "picked_up"), ev(T("19:10", "2026-10-21"), "handoff", method="in_person")])
order("K-6104", "E317", "S9", [("Chicken pho", 1, 14.50), ("Iced coffee", 1, 4.75)],
      T("12:10"), T("12:55"), "delivered", record_delivered=T("12:50"),
      events=[ev(T("12:20"), "item_unavailable", item="Iced coffee", note="Restaurant marked unavailable"),
              ev(T("12:31"), "picked_up"), ev(T("12:50"), "handoff", method="in_person")],
      auto_refunds=[{"amount": 4.75, "item": "Iced coffee", "time": T("12:21"),
                     "reason": "item unavailable; refunded automatically to card"}])
# X18: office order, $160 subtotal, $16 promo (10%); four items missing or wrong, two horchatas auto-refunded
order("K-6201", "E318", "S3", [("Carne asada tacos", 6, 4.50), ("Chicken tacos", 6, 4.00), ("Veggie burrito", 2, 12.00),
                               ("Chips and guacamole", 3, 7.00), ("Elote", 4, 5.00), ("Horchata", 4, 4.00),
                               ("Cheese quesadilla", 2, 10.00), ("Churros", 2, 4.00)],
      T("11:40"), T("12:30"), "delivered", promo=("OFFICE16", 16.00), tip=12.00, record_delivered=T("12:24"),
      events=[ev(T("11:58"), "item_unavailable", item="Horchata", qty=2, note="Restaurant marked 2 unavailable"),
              ev(T("12:05"), "picked_up"), ev(T("12:24"), "handoff", method="in_person")],
      auto_refunds=[{"amount": 8.00, "item": "Horchata x2", "time": T("11:59"),
                     "reason": "item unavailable; refunded automatically to card"}])
# X19: three live problems: cancel one (not picked up), address change on one already picked up (status is stale),
# and a lost order to replace (placed today, restaurant open until 21:30)
order("K-6301", "E319", "S2", [("Pad thai", 1, 13.50), ("Tom kha soup", 1, 9.00)],
      T("19:05"), T("19:50"), "preparing", events=[ev(T("19:07"), "courier_assigned")])
order("K-6302", "E319", "S7", [("Classic burger", 1, 12.00), ("Sweet potato fries", 1, 5.50)],
      T("18:50"), T("19:35"), "preparing",
      events=[ev(T("18:52"), "courier_assigned"), ev(T("19:20"), "picked_up")])
order("K-6303", "E319", "S6", [("Harvest bowl", 1, 14.00), ("Green juice", 1, 6.50)],
      T("17:30"), T("18:15"), "delivery_failed",
      events=[ev(T("17:32"), "courier_assigned"), ev(T("17:58"), "picked_up"),
              ev(T("18:40"), "order_lost", note="Courier reported the bag was stolen from the bike; not delivered.")])
# X20: long refund history (13 entries, only 2 support refunds in the window); an order lost tonight
order("K-6401", "E320", "S10", [("Dragon roll", 1, 16.00), ("Salmon nigiri", 2, 6.00), ("Edamame", 1, 5.00),
                                ("Miso soup", 2, 3.50)],
      T("18:00"), T("18:45"), "delivery_failed",
      events=[ev(T("18:02"), "courier_assigned"), ev(T("18:25"), "picked_up"),
              ev(T("19:02"), "order_lost", note="Courier abandoned the delivery; the order was not delivered.")])
# X21: Plus member; four orders this week: capped 20%, tier 1, ETA-updated (not late), and out of the 7-day window;
# plus a missing item that would take credit over the $40 Plus conversation limit
order("K-6501", "E321", "S1", [("Family thali", 2, 32.00), ("Lamb biryani", 2, 18.00), ("Garlic naan", 4, 4.00),
                               ("Gulab jamun", 2, 6.00)],
      T("17:10"), T("18:00"), "delivered", record_delivered=T("18:50"),
      events=[ev(U("00:12", "2026-10-25"), "courier_assigned"), ev(U("01:30", "2026-10-25"), "picked_up"),
              ev(U("01:52", "2026-10-25"), "handoff", method="in_person")])
order("K-6502", "E321", "S9", [("Beef pho", 1, 15.50), ("Summer rolls", 1, 9.00), ("Thai iced tea", 1, 4.00)],
      T("18:30", "2026-10-22"), T("19:15", "2026-10-22"), "delivered", record_delivered=T("19:45", "2026-10-22"),
      events=[ev(T("19:22", "2026-10-22"), "picked_up"), ev(T("19:45", "2026-10-22"), "handoff", method="in_person")])
order("K-6503", "E321", "S3", [("Carnitas burrito", 1, 13.00), ("Elote", 1, 5.00)],
      T("17:45", "2026-10-20"), T("18:30", "2026-10-20"), "delivered", record_delivered=T("19:12", "2026-10-20"),
      events=[ev(T("17:50", "2026-10-20"), "eta_updated", new_eta=T("19:00", "2026-10-20"),
                 reason="Courier shortage", notified_customer=True, channel="push notification"),
              ev(T("18:55", "2026-10-20"), "picked_up"), ev(T("19:12", "2026-10-20"), "handoff", method="in_person")])
order("K-6504", "E321", "S7", [("Double cheeseburger", 1, 14.50), ("Onion rings", 1, 6.00)],
      T("18:15", "2026-10-16"), T("19:00", "2026-10-16"), "delivered", record_delivered=T("20:00", "2026-10-16"),
      events=[ev(T("19:40", "2026-10-16"), "picked_up"), ev(T("20:00", "2026-10-16"), "handoff", method="in_person")])
# X22: three orders tonight; one inside the Spice Route incident window (placed 18:58), one just after it (19:02)
order("K-6601", "E322", "S4", [("Paneer makhani", 1, 15.00), ("Jeera rice", 1, 4.50)],
      T("18:58"), T("19:40"), "delivered", record_delivered=T("19:24"),
      events=[ev(T("19:10"), "picked_up"), ev(T("19:24"), "handoff", method="in_person")])
order("K-6602", "E322", "S4", [("Garlic naan", 2, 4.00), ("Mango lassi", 1, 4.50)],
      T("19:02"), T("19:45"), "delivered", record_delivered=T("19:24"),
      events=[ev(T("19:10"), "picked_up"), ev(T("19:24"), "handoff", method="in_person")])
order("K-6603", "E322", "S2", [("Green curry", 1, 15.00), ("Spring rolls", 1, 7.00)],
      T("18:30"), T("19:15"), "delivered", record_delivered=T("19:12"),
      events=[ev(T("18:55"), "picked_up"), ev(T("19:12"), "handoff", method="in_person")])

TICKETS = [
    {"ticket_id": "TK-1201", "customer_id": "E306", "created_at": T("19:02"), "order_id": "K-8601",
     "summary": "Customer said the order was very late and still hadn't arrived.",
     "agent_actions": ["Issued $6.40 account credit (20% of the $32.00 subtotal) for the delay."], "promises": []},
    {"ticket_id": "TK-1144", "customer_id": "E302", "created_at": T("20:10", "2026-10-15"), "order_id": "K-7511",
     "summary": "Wrong side delivered.", "agent_actions": ["Refunded $6.25 to card."], "promises": []},
    {"ticket_id": "TK-0990", "customer_id": "E313", "created_at": T("12:05", "2026-09-30"), "order_id": None,
     "summary": "Asked how to change the default delivery address.", "agent_actions": ["Explained the steps."],
     "promises": []},
    {"ticket_id": "TK-1188", "customer_id": "E316", "created_at": T("18:40", "2026-10-20"), "order_id": "K-7790",
     "summary": "Missing item.", "agent_actions": ["Refunded $5.50 to card."], "promises": []},
    {"ticket_id": "TK-1172", "customer_id": "E320", "created_at": T("20:00", "2026-10-19"), "order_id": "K-5760",
     "summary": "Wrong entree.", "agent_actions": ["Refunded $14.00 to card."], "promises": []},
    {"ticket_id": "TK-1103", "customer_id": "E320", "created_at": T("18:55", "2026-09-24"), "order_id": "K-5512",
     "summary": "Missing item.", "agent_actions": ["Refunded $11.00 to card."], "promises": []},
]
PRIOR_CREDITS = {"E306": [{"amount": 6.40, "reason": "late_delivery", "order_id": "K-8601", "item_ids": [],
                           "created_at": T("19:04")}]}
ACTIVITY = {
    "E310": [
        {"time": T("09:30", "2026-03-02"), "type": "password_changed", "device": "iPhone, Oakdale, CA (known device)"},
        {"time": T("16:25"), "type": "password_reset", "device": "New device: Android, Phoenix, AZ"},
        {"time": T("16:28"), "type": "phone_changed", "from": "+1 415-555-0310", "to": "+1 415-555-0910",
         "device": "New device: Android, Phoenix, AZ"},
    ],
    "E309": [{"time": T("11:00", "2025-06-02"), "type": "authorized_user_added", "detail": "Ken Tanaka",
              "device": "iPhone, Oakdale, CA (known device)"}],
    "E304": [{"time": T("14:12", "2026-09-18"), "type": "email_changed", "from": "ruby.a@post.example",
              "to": "ruby.alvarez@inbox.example", "device": "Mac, Oakdale, CA (known device)"}],
}


def main() -> None:
    for c in CUSTOMERS:
        ledger = PRIOR_CREDITS.get(c["customer_id"], [])
        c["credit_balance"] = round(sum(e["amount"] for e in ledger), 2)
        c["credit_ledger"] = ledger
    for o in ORDERS:
        o["credits"] = [e for c in CUSTOMERS for e in c["credit_ledger"] if e["order_id"] == o["order_id"]]
    world = {"suite": "v3food", "now": NOW, "restaurants": RESTAURANTS, "customers": CUSTOMERS, "orders": ORDERS,
             "delivery_events": EVENTS, "payments": PAYMENTS, "tickets": TICKETS, "account_activity": ACTIVITY,
             "escalations": [], "replacements": []}
    out = Path(__file__).resolve().parents[1] / "world" / "v3food" / "base.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(world, indent=1) + "\n")
    print(f"wrote {out}")
    for o in ORDERS:
        print(o["order_id"], o["customer_id"], o["status"], "sub", o["subtotal"], "promo", o["promo_discount"],
              "fee", o["delivery_fee"], "svc", o["service_fee"], "tip", o["tip"], "total", o["total"])


if __name__ == "__main__":
    main()
