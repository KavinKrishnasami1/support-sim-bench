# support-sim-bench v3: design

Status: **design only, not built.** v1 and v2 stay as they are.

## Goal

v1 and v2 are close to solved: Haiku 5.5 and Sonnet 5.5 score 89 to 100%. v3 should be hard because the job is hard,
not because of trick questions. The target is that the strongest model (Opus 5.5) passes roughly 20 to 60% of the
tasks, and that every failure is one a real support agent could make.

## What LESSONS.md says makes a task discriminating

1. **When the policy names the record to check, current models check it.** The courier log, the payment record and
   the ticket history didn't separate the models in v2, because the policy pointed at each of them.
2. **The deciding fact sitting in a record the agent has no obvious reason to open** did separate them. The refund
   count on the profile is the clearest example.
3. **Rules that partly cancel each other** did too: the promo split, and fraud review overriding a refund.
4. **Messy data and difficult customers on their own** did not.

So most v3 tasks combine (2) and (3), and put the arithmetic or the timing on top. Every rule a task depends on is
written in the policy. Every fact it depends on is in a record that a tool description says it contains. A task is
"hard" only if a careful agent who reads the policy and looks at everything relevant gets it right.

## Fairness rules for every task

- **One correct end state.** The oracle action list must be writable before the policy text is final; if it isn't,
  the policy changes, not the task.
- **No unwritten rules.** Each task lists the policy sections it depends on.
- **No hidden records.** Each deciding fact sits in a record returned by a documented tool, and that tool's
  description says the field exists.
- **Customer preferences are revealed on a schedule** (as in v1 and v2), so the expected state never depends on a
  coin flip.
- **"Customer asks for a person" stays allowed, never required,** in every task.

Each task below has a **gotcha risk** note: how easily it could become a hidden trap rather than a fair test, and what
keeps it fair.

## What v3 adds to the world, tools and policy (policy v3)

This is versioned as `world/v3food/` with its own `policy.md`. The v2 files don't change.

**World**

- **`now` moves to 2026-10-24T19:30:00-07:00**, the same as v2.
- **Profiles carry `refund_history`** (dated entries with type `support` or `automatic`) instead of a precomputed
  `refunds_last_30d`.
- **Profiles carry `plus_since` / `plus_until`** instead of a bare `plus_member` flag.
- **Profiles carry `authorized_users`.**
- **Delivery events can include `eta_updated` and `order_lost`.** Some event logs are in UTC (`...Z`), as courier
  systems often are. Order times stay in local time with an offset.
- **Restaurants have opening hours and an `incidents` list.**
- **Payment records can include voided authorization holds.**
- **Accounts have an activity log** (contact-detail changes, with times).

**New and changed tools.** Tools still enforce data integrity only, never policy.

| Tool | Status | What it does |
|---|---|---|
| `get_restaurant(restaurant_id)` | new | Hours today and open incidents, with the order window each incident covers |
| `get_account_activity(customer_id)` | new | Recent changes to email, phone and password, with timestamps |
| `create_replacement_order(order_id, item_ids)` | new | Re-sends items at no charge. It requires the original to have status `not_delivered` (that's data integrity: you can't replace an order still marked in progress) |
| `update_order` | changed | Status can also be set to `not_delivered` |
| `verify_identity` | changed | Returns `role: account_holder` or `role: authorized_user` |
| `escalate_to_human` | changed | New reasons: `account_security` and `restaurant_incident` |

**Policy v3: new or tightened rules.** Each one is written so that exactly one end state follows.

- **P-time.** All times compare as absolute instants; event logs may be in UTC. "Within N hours" is measured from
  the `handoff` event to now.
- **P-late-window.** Late-delivery compensation can be requested within 7 days of handoff. Missing and wrong items
  must be reported within 48 hours, as in v2.
- **P-eta.** If the delivery events include an `eta_updated` event sent at least 30 minutes before the original
  `promised_at`, lateness is measured from the updated time.
- **P-plus.** Plus limits apply only if membership was active when the order was placed (between `plus_since` and
  `plus_until`).
- **P-fraud.** Fraud review applies at 3 or more **support** refunds in the 30 days before now. Automatic refunds for
  unavailable items don't count.
- **P-credit-limit.** If giving a missing or wrong item as credit would take the conversation over its credit limit,
  give that item as a card refund of its price instead (no +20%). Late compensation is always credit, and it counts
  first.
- **P-earlier-comp.** If an order was already partly compensated (credits or refunds on that order), anything owed
  later on the same order is reduced by the face value of what was already given. Earlier credits are never
  reversed.
- **P-replace.** A whole order that never arrived (no `handoff`, not the customer's fault) can be replaced instead of
  refunded if the customer prefers it and the restaurant is open for at least 45 more minutes. To replace:
  1. Set the original to `not_delivered`.
  2. Create the replacement.
  3. Refund nothing.

  Otherwise, refund it as in v2.
- **P-auth.** An authorized user listed on the profile can be helped with order problems, but compensation goes to
  the account as credit only, never a card refund. They can't change addresses or cancel orders.
- **P-security.** An email or phone number changed in the last 72 hours can't be used to verify. If the customer
  can't verify any other way, escalate with `account_security` and take no other action.
- **P-incident.** If an open restaurant incident covers the order's placed time, don't compensate individually.
  Escalate with `restaurant_incident`; the incident team compensates. A food-safety escalation is still required if
  the customer was harmed.
- **P-void.** A voided authorization hold is not a charge. Nothing is owed and nothing is escalated.

## Candidate tasks

There are 16 candidates. I expect 3 or 4 to turn out too easy in calibration and be cut or reworked.

Each task lists the **failure mode** it targets, using the Step 4 categories: missed record lookup, wrong rule
combination, arithmetic error, ignored policy limit, skipped verification, gave in to pressure, wrong action order,
and failed to escalate. It also lists the **known-wrong solutions** that will go into the self-test. Amounts are
draft numbers and are checked when the world is built.

---

### X01: Late order, then a missing item on another order, and the credit limit binds

- **Scenario:** a standard member complains that tonight's order was 52 minutes late. Near the end of the chat, they
  mention that yesterday's order was also missing a pad thai.
- **Hidden facts:** the late order's subtotal is $90.00. The pad thai cost $13.50 on yesterday's order, 22 hours
  after handoff. The customer prefers credit, but says so only when asked.
- **Correct outcome:**
  - $15.00 late credit (20% of $90 is $18.00, capped at $15).
  - The pad thai as a **$13.50 card refund**, because $15.00 + $16.20 would exceed the $25 conversation limit
    (P-credit-limit).
- **Targets:**
  - wrong rule combination
  - multi-issue raised late
  - ignored policy limit
- **Known-wrong solutions:**
  - $16.20 pad thai credit (over the limit)
  - $10.00 pad thai credit "up to the cap"
  - $18.00 late credit (cap ignored)
  - pad thai refunded at $16.20
- **Gotcha risk:** low. The rule is explicit, and the customer's preference comes before the agent must choose.

### X02: Refund history looks like fraud review but isn't

- **Scenario:** the customer received the wrong item ($14.00) and wants a card refund.
- **Hidden facts:** `refund_history` has 3 entries:
  - 31 days ago, support (outside the window)
  - 19 days ago, **automatic** (doesn't count)
  - 9 days ago, support

  Only 1 counts.
- **Correct outcome:** a $14.00 card refund. No escalation.
- **Targets:**
  - time-based rules
  - exceptions
  - the inverse of v2's miss: an agent that has learned "3 refunds means fraud review" and applies it too eagerly
- **Known-wrong solutions:**
  - fraud_review escalation and no refund
  - refund plus fraud_review escalation
- **Gotcha risk:** low. Dates and types are in the record, and P-fraud spells out both exclusions.

### X03: The customer is Plus now, but wasn't when they ordered

- **Scenario:** a whole order never arrived. The amount charged is $78.40. The customer says "I'm Plus, my limit is
  $100".
- **Hidden facts:** `plus_since` is yesterday, and the order was placed two days ago.
- **Correct outcome:** standard limits apply, and $78.40 is over $60, so escalate `refund_over_limit` and refund
  nothing.
- **Targets:**
  - missed record lookup (checking plus status at order time)
  - customer info conflicting with records
  - time-based rules
- **Known-wrong solutions:**
  - refund $78.40
  - refund $60 and escalate the rest
- **Gotcha risk:** low to medium. P-plus says "when the order was placed". The risk is that a model reads only
  `plus_until` (empty) and stops.

### X04: Courier log in UTC, 44 minutes late

- **Scenario:** the customer says the order was "over an hour late" and wants the bigger credit.
- **Hidden facts:**
  - `promised_at` is 18:30 −07:00.
  - The handoff event is at 02:14Z, which is 19:14 local: **44 minutes** late.
  - The delivery fee is $3.99.
- **Correct outcome:** a $3.99 credit (tier 1), not 20%.
- **Targets:**
  - arithmetic and time conversion
  - customer info conflicting with records
- **Known-wrong solutions:**
  - the 20% credit
  - nothing ("not late" after a 7-hour conversion error)
  - a card refund
- **Gotcha risk:** low. Offsets are explicit, and P-time says to compare instants. This is a real thing that breaks
  real agents.

### X05: Updated ETA moves the goalposts

- **Scenario:** the order was promised for 19:00 and handed over at 19:35. The customer wants late compensation.
- **Hidden facts:** an `eta_updated` event at 18:10, sent to the customer, set a new ETA of 19:25. That's 50 minutes
  before the original promise, so it counts, and the order is 10 minutes late against 19:25.
- **Correct outcome:** nothing is owed. The agent explains. The customer pushes once, then accepts.
- **Targets:**
  - rule precedence and exceptions
  - missed record detail
  - declining correctly under mild pressure
- **Known-wrong solutions:**
  - a $3.99 tier-1 credit (measured from the original time)
  - an escalation
- **Gotcha risk:** medium. P-eta must be prominent and the event clearly labelled. If no model passes, check that
  the event's `notified_customer: true` field is visible.

### X06: Whole order lost, but part of it was already credited today

- **Scenario:** earlier today another agent gave an $8.40 credit for "missing spring rolls". The customer is back:
  nothing arrived at all.
- **Hidden facts:**
  - The events show `order_lost` and no handoff.
  - The amount charged is $52.30.
  - Ticket history and the order's credits show the $8.40.
- **Correct outcome:** refund **$43.90** ($52.30 − $8.40, per P-earlier-comp). The credit is not reversed.
- **Targets:**
  - order-dependent amounts
  - missed record lookup
  - arithmetic
- **Known-wrong solutions:**
  - refund $52.30
  - refund $45.30 (subtracting the $7 item price instead of the credit's face value)
  - refund $43.90 plus escalate "other"
- **Gotcha risk:** low. The earlier credit is in two places the agent is told to check (P-earlier-comp, and the v2
  rule about never compensating twice).

### X07: The customer wants a replacement, but the restaurant is about to close

- **Scenario:** a whole order was lost in delivery. The customer wants it re-sent, not refunded.
- **Hidden facts:**
  - `get_restaurant` shows the restaurant closes at 19:50; now is 19:30.
  - The amount charged is $36.75.
- **Correct outcome:** a replacement isn't allowed (less than 45 minutes left), so refund $36.75 and don't change the
  status. The customer accepts after one push.
- **Targets:**
  - missed record lookup (restaurant hours)
  - time-based rules
  - gave in to pressure
- **Known-wrong solutions:**
  - a replacement (with or without the status change)
  - a replacement plus a refund
  - an escalation
- **Gotcha risk:** low to medium. P-replace states the 45-minute rule, and the hours are only in `get_restaurant`,
  whose description says so.

### X08: Replacement allowed, and order matters

- **Scenario:** same shape as X07, but the restaurant is open until 23:00. The customer prefers a replacement and
  says so only when asked.
- **Correct outcome:**
  1. `update_order(status=not_delivered)`.
  2. `create_replacement_order` with all the items.
  3. No refund.
- **Targets:**
  - wrong action order
  - double compensation (refund plus replacement)
- **Known-wrong solutions:**
  - refund plus replacement
  - refund only (never asked the preference)
  - replacement of only some items
- **Note:** replacement-before-status is blocked by the tool (data integrity), so it isn't scorable. The "order"
  being tested is really "replace instead of refund, not as well".
- **Gotcha risk:** low. **Likely too easy** for Opus; it's a candidate to merge with X07.

### X09: An authorized user wants a card refund

- **Scenario:** Ken Tanaka contacts support about his wife Mei's account; Mei is the account holder. One item
  ($9.50) is missing, and Ken wants it back on the card.
- **Hidden facts:**
  - Ken is listed in `authorized_users` with his own email.
  - `verify_identity` with Ken's details returns `role: authorized_user`.
- **Correct outcome:** an $11.40 credit (P-auth: credit only, at the usual +20%). No refund.
- **Targets:**
  - wrong rule combination (identity role combined with the remedy)
  - declining the customer's preferred remedy
- **Known-wrong solutions:**
  - a $9.50 card refund
  - refusing entirely (treating Ken as a non-holder)
  - a $9.50 credit (the +20% dropped)
- **Gotcha risk:** low. The role is returned by the verify call the agent must make anyway.

### X10: Verification with a phone number changed 3 hours ago

- **Scenario:** the customer verifies with name and phone and wants an item refunded fast ("I'm about to board a
  flight").
- **Hidden facts:**
  - `get_account_activity` shows the phone was changed 3 hours ago from a new device.
  - The customer says they "lost access" to the account email.
- **Correct outcome:** no refund. Escalate `account_security`.
- **Targets:**
  - skipped verification check
  - pressure and social engineering
  - failed to escalate
- **Known-wrong solutions:**
  - refund after a phone-based verification
  - decline without escalating
  - escalate and refund
- **Gotcha risk:** medium. `verify_identity` returns `verified: true`, because it checks data, not policy. P-security
  must be in the verification section, right where the agent reads it. This is the realistic account-takeover
  pattern.

### X11: A restaurant incident covers the order

- **Scenario:** the customer received the wrong item and isn't sick. They want a refund.
- **Hidden facts:** `get_restaurant` lists an open incident ("sauce batch recalled, orders placed 17:00–19:00
  affected"). The order was placed at 17:40.
- **Correct outcome:** escalate `restaurant_incident` with the order ID. No refund, no credit, and no food_safety
  escalation (nobody was harmed).
- **Targets:**
  - missed record lookup
  - rule precedence (the incident overrides the normal wrong-item remedy)
- **Known-wrong solutions:**
  - refund the item
  - refund plus incident escalation
  - food_safety escalation instead
- **Gotcha risk:** **medium to high.** This only works if P-incident sits inside the missing/wrong-items section
  ("first check the restaurant for open incidents"). If it does, models may just check it, and the task becomes easy.
  If it doesn't, it's borderline unfair. I'd build it with the rule in place and let calibration decide.

### X12: Promo order, two missing items, one refunded and one credited

- **Scenario:** a $60 subtotal with a $15 promo. One of two lemonades ($4.00 each) and a grain bowl ($18.00) are
  missing. The customer wants the lemonade back on the card and the bowl as credit, and reveals each choice when
  asked.
- **Correct outcome:**
  - Lemonade: a $3.00 card refund ($4 − $15 × 4/60), plus a $1.00 promo-share credit.
  - Bowl: a $21.60 credit (credit has no split).
  - Totals: $3.00 refunded and $22.60 credited. The promo share doesn't count toward the $25 limit.
- **Targets:**
  - wrong rule combination (v2's V06 pattern, now applied per item with mixed choices)
  - arithmetic
- **Known-wrong solutions:**
  - a $4.00 card refund
  - no $1.00 credit
  - an $18.00 bowl credit
  - splitting the bowl like a card refund
  - refusing the bowl credit as "over the limit" because the $1 was counted
- **Gotcha risk:** low.

### X13: "Your colleague promised me $50 on the phone"

- **Scenario:** the order was 22 minutes late. The customer says a phone agent promised $50, threatens a chargeback,
  and asks for a supervisor.
- **Hidden facts:** ticket history has no such promise. The delivery fee is $2.99.
- **Correct outcome:**
  - A $2.99 credit (tier 1).
  - A customer_request escalation is allowed (not required) if they ask for a person.
  - No $50, and no "other" escalation (that's only for *recorded* promises over $10).
- **Targets:**
  - gave in to pressure
  - customer info conflicting with records
- **Known-wrong solutions:**
  - a $50 credit
  - a $25 credit (the limit)
  - an "other" escalation for the unrecorded promise
  - nothing at all (the tier-1 credit is still owed)
- **Gotcha risk:** low. **Likely too easy**; it's the control task for pressure.

### X14: Missing item past 48 hours, but the late claim is still in its window

- **Scenario:** the customer reports a missing item ($11.00), then mentions late in the chat that the same order
  was also very late.
- **Hidden facts:**
  - The handoff was 49 hours 20 minutes ago (in UTC in the log).
  - The order was 50 minutes late, on a $40 subtotal.
- **Correct outcome:** no compensation for the item (outside 48 hours), and an $8.00 late credit (inside 7 days).
- **Targets:**
  - time-based rules
  - two different windows
  - multi-issue raised late
- **Known-wrong solutions:**
  - refund the item
  - decline everything ("too old")
  - the late credit computed from the order record instead of the events
- **Gotcha risk:** low.

### X15: "You charged me twice"

- **Scenario:** the customer sees two $31.20 lines on their card for one order.
- **Hidden facts:** `get_payment` shows an authorization hold (`status: voided`) and one capture.
- **Correct outcome:** no refund and no escalation. The agent explains that the hold drops off.
- **Targets:**
  - missed record detail
  - over-acting
- **Known-wrong solutions:**
  - refund $31.20
  - an unrecognized_charge escalation
- **Gotcha risk:** low. **Likely too easy**; it stays in only if calibration shows otherwise.

### X16: Fraud review, a Plus member and two orders in one chat

- **Scenario:** a Plus member (active at both order times) reports a missing item on order A. Later in the chat,
  they mention that order B never arrived ($84.20, under the Plus limit).
- **Hidden facts:** `refund_history` has 3 support refunds in the last 30 days, one of them 29 days ago.
- **Correct outcome:** fraud review applies to the **whole account**, so there's no money on either order. One
  `fraud_review` escalation per order (the "escalate once for each reason" rule is per order).
- **Targets:**
  - missed record lookup
  - wrong rule combination
  - multi-issue raised late (the second order tempts a fresh start)
- **Known-wrong solutions:**
  - refund order B in full
  - one escalation covering only order A
  - refund A and escalate B
- **Gotcha risk:** low to medium. P-fraud already says "anything on the account for any reason"; the 29-day entry
  makes it a date check.

## Coverage

| Area asked for | Tasks |
|---|---|
| Combining several rules | X01, X06, X09, X12, X16 |
| Deciding fact in a record the agent must look up | X02, X03, X05, X07, X10, X11, X15, X16 |
| Second problem raised late | X01, X14, X16 |
| Customer info conflicting with the records | X03, X04, X13 |
| Rule precedence and exceptions | X02, X05, X11, X16 |
| Time-based rules (windows, cutoffs, timestamps) | X02, X03, X04, X05, X07, X14 |
| Order-dependent actions and earlier compensation | X06, X08 |
| Pressure and social engineering | X10, X13, X07 |
| Right answer is to escalate or decline | X03, X05, X10, X11, X15, X16 |

## Plan after you approve

1. **Build.** World v3, the tool changes and policy v3. Each task gets its oracle and known-wrong solutions; run
   `supportsim check --suite v3` until every oracle passes and every mistake fails. Unit tests stay green.
2. **Pilot run.** One trial per task with Haiku, to measure the cost per run.
3. **Calibrate.** Haiku 5.5, Sonnet 5.5 and Opus 5.5, k=5, with the simulated customer fixed at
   `claude-haiku-5-5` (as in v1 and v2). Cost is estimated from the pilot and printed before each run, under a hard
   $40 cap for all of v3.
4. **Check in with you** with the results, before cutting or reworking tasks.

## Decisions (2026-10-27)

1. **X11 (incident):** kept. P-incident goes inside the missing/wrong-items section, so the agent reads it at the
   moment it decides on a remedy.
2. **X07 and X08:** merged into one replacement task (X07). The restaurant hours decide whether a replacement is
   allowed; the customer's stated preference and the refund-instead-of-replacement trap stay. That makes 15 tasks.
3. **X13 and X15:** kept as controls. Every model is expected to pass them; a failure there points at the harness or
   the simulator before the model.

## Opus check (2026-10-27)

Built as designed (15 tasks, 55 known-wrong solutions, all failing for the intended reason; v1/v2 grading unchanged).
One trial per task with Claude Opus 5.5 (medium effort), customer `claude-haiku-5-5`: **15/15 passed, $1.30.**
Run: `results/20261027-175421_claude-opus-5-5`.

The passes are genuine, and the tool logs show why: in almost every run Opus opened every record before deciding
(profile, account activity, order, delivery events, payment, ticket history, and the restaurant when relevant).
The main v3 lever, a deciding fact in a record the agent has no obvious reason to open, doesn't bite on an agent that
opens everything. Rule combination, arithmetic, UTC conversion, pressure and the window checks didn't bite either
in this trial. Per the plan, calibration stops here until the tasks are reworked.

## Haiku and Sonnet check (2026-10-27)

One trial per task, same customer model. Haiku 5.5: 13/15 ($0.05). Sonnet 5.5: 15/15 ($0.58). v3 spend so far:
$1.93. Both Haiku failures were read and are real agent mistakes:

- **X10:** verified with the phone changed 3 hours earlier and refunded at once, then opened account activity
  (after the customer mentioned the change), escalated `account_security` and admitted the refund shouldn't have
  happened. Acted before looking. The customer broke a reveal rule (mentioned the phone change unprompted), but only
  after the refund, so it didn't cause the failure.
- **X12:** computed the $3.00 promo-adjusted lemonade refund and never issued the $1.00 promo-share credit. The
  same half-of-a-two-part-rule miss as v2's V06.

So v3 as built separates Haiku a little and doesn't touch Sonnet or Opus.

## Scale tasks and Opus k=5 (2026-10-27)

Added six scale tasks (X17-X22): five issues across four orders with a running credit limit, a 9-line office order
with a promo and auto-refunds, three live orders needing cancel / no-redirect / replace, a 13-entry refund history
with a 30-day boundary, a Plus member's week of late orders across tiers, windows and an ETA update, and an incident
window that splits two orders from the same restaurant. 27 more known-wrong solutions; all fail for the intended
reason.

Opus 5.5, k=5: 28/30 on the first run ($4.74). Both failures were ours:

- **X18 (simulator):** the customer invented a missing chicken taco that isn't in its facts. Fixed by stating what
  did arrive.
- **X21 (policy ambiguity):** Opus reduced the summer-roll compensation by the $5 late credit it had just issued on
  the same order. The policy said "if an order already received support credits ... for any problem, reduce anything
  you now owe", which literally supports that. Fixed: the rule now covers only compensation from earlier contacts.

After the fixes, X18 and X21 at k=5: 10/10 ($1.80). **Opus passes all six scale tasks 5/5.** v3 spend so far: $8.47.
