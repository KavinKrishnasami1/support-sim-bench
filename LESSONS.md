# What was hard

Notes from building a 13-task, tau-bench-style support benchmark over a weekend. Written for conversations with
people who build agent tasks and environments. Sections 1 to 4 come from building the tasks. Section 5 will come
from running models.

## 1. Writing the policy: every rule had a hole until a task hit it

The first draft of the policy read fine and was ambiguous almost everywhere a task touched it. Each of these had to
become explicit before a task could have exactly one correct final state:

- **"Late."** Late by how much, measured from what? It became "delivered more than 15 minutes after
  `promised_at`", with two tiers (16 to 44 minutes, 45 or more) and a cap. Without a fixed "now" in the world,
  "late" and "within 48 hours" drift with the wall clock and the same run grades differently tomorrow.
- **"Refund the item."** One lemonade or both? Is tax or the service fee included? It became "unit price × quantity
  affected", with fees refunded only when every item was missing.
- **Refund or credit.** If the policy lets the customer choose, the expected state depends on a hidden
  preference, so the scenario has to say when the customer reveals it. Otherwise "correct" is a coin flip.
- **Escalation versus acting.** "Escalate refunds over $60" left open whether the agent may refund $60 and
  escalate the rest. It had to say "instead of refunding anything yourself" for one set of triggers and "in
  addition to resolving" for another (food safety, a request for a person).
- **"Speak to a manager" is a trigger.** In the address-after-pickup task the customer originally asked for a
  manager, which made an escalation mandatory and changed the expected state. We removed the ask rather than make
  the task about two things at once. Every natural customer line has to be checked against the policy's triggers.
- **Caps per what?** "$25 credit limit" per call, per order, or per conversation? Per call is trivially dodged by
  issuing two credits, so it is per conversation, summed by the grader.
- **No goodwill.** Without an explicit "no compensation for reasons not listed", a kind agent that adds $5 for
  the trouble is arguably fine, and the expected state is unknowable.

Lesson: write the oracle actions for a task before you finalize its policy text. Ambiguity shows up as "I can't
write down the one correct sequence."

## 2. Grader loopholes, found by writing down wrong answers

Each task carries named "mistakes", the wrong action sequences we expect agents to try, and a check that all 38
of them fail. Writing them exposed holes a final-state-only grader would have missed:

| Loophole | What would have passed | Fix |
|---|---|---|
| Final state can't see order of operations | Refund first, verify identity afterwards: the same final state as doing it right | Action check: every write must come after a successful `verify_identity` for that customer |
| Splitting compensation | Two credits of $15 and $10 where policy caps at $15 | Sum per customer; conversation-wide cap check |
| Partial action plus escalation | Refund $60, then escalate the rest of a $131 order | Expected refunds are exact (zero here), not "at most" |
| Escalation as a catch-all | Escalating every case, or with reason "other" | Escalations are matched exactly on order and reason; extras allowed only where the task says so |
| Unusable escalations | "Whole office order missing" with no order ID | Summary must contain the order ID |
| Tools that enforce policy | If `update_order` refused picked-up orders, an agent that tries anyway looks perfect | Tools enforce data integrity only; policy violations reach the grader |
| Formatting | Grading by exact string fails correct agents that write `5102` instead of `O-5102`, or "Ste 310" | Normalize IDs; match addresses on required and forbidden words |

The cheapest grader test we found: replay the oracle, which must pass, and the mistakes, which must fail, through
the real tools with no model in the loop. It costs nothing and catches most holes before any API spend.

## 3. Simulator realism (design side)

- **Facts versus reveal rules.** A customer that knows everything dumps it in the first message, and the task
  stops testing whether the agent asks. Each scenario separates what the customer knows from when they say it
  ("mention the lemonades only if asked whether anything else was missing, or after a resolution that covers only
  the wrap").
- **The simulator must not know the answer.** It is never told the policy or the remedy, only its own goal, such as
  "you want a $40 credit". Even so, a customer told to accept "if the agent explains why" can nudge a weak agent.
  That's why runs are flagged when the customer says an expected amount or a policy phrase before the agent does.
- **Plausible mistakes need scripting.** Real customers give the wrong suite number, misremember amounts, and use
  someone else's account (all seen in the source chats). A simulator won't do this unless the scenario says exactly
  when and how.
- **Leak checks must be order-aware.** A customer quoting the agent's own offer back ("ok, $3.99 works") is fine. The
  same amount before the agent said it is a leak. The first version flagged both.
- **The simulator and the database must agree.** The customer's facts (times, items, prices) and the world were
  written separately, so drift between them is a constant risk. One source of truth for both would be better.

## 4. Source data

Deriving scenarios from real support chats (ABCD, MIT-licensed) gave realistic customer behaviour, but the agents in
those chats are not ground truth: in the "charged for something I never bought" chat, the agent credits the money
back without any checks. Real transcripts are good for the customer side and for which situations occur. They are
poor as labels for what the agent should have done; that comes from the policy.

## 5. From the runs

To be filled in after running models (see RESULTS.md): where agents fail, whether the simulator stayed in character,
how often it leaked, and what a run costs.
