# What was hard

Notes from building a tau-bench-style support benchmark over a weekend: a 13-task v1 and a harder 12-task v2.
Written for conversations with people who build agent tasks and environments. Sections 1 to 4 come from building
the v1 tasks. Section 5 comes from the first runs on v1, and section 6 from building and running v2. Final numbers
are in RESULTS.md.

**The short version:**

- Most of what first looked like model failures were benchmark bugs: in the grader, the policy, the harness or the
  simulator.
- Realistic complexity (conflicting records, wrong customers) didn't separate the models. Two things did: combining
  rules, and a deciding fact sitting in a record the agent had no reason to open.
- Three trials per task is too few to rank two good models.

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

## 5. First runs (v1)

We ran Claude Haiku 5.5 and Claude Sonnet 5.5 as agents, 13 tasks × 3 trials each, for $0.89 in total. The
numbers in this section are from that first round; RESULTS.md has the final ones.

**Most first-pass failures were ours.** The first grading said Haiku 77%, Sonnet 90%. Reading every failing
transcript showed that 10 of the 13 failures were benchmark bugs:

- 7 runs: the agent did what the policy literally asked (order ID in the escalation summary) and left the optional
  `order_id` field empty, but the grader required the field.
- 1 run: a scripted customer line ("I need to talk to someone") quietly triggered a policy rule (escalate when
  asked for a person) that the task didn't expect.
- 2 runs: an agent filed a follow-up "addendum" escalation for the same case, and the grader counted escalations as
  a list instead of a set.

After fixes, both models scored 92–97%. Without reading transcripts we would have published a 13-point gap between
the models that was mostly grader noise. **The replay-based regrade** (re-run the logged tool calls through the
current grader, no model calls) made fixing this cheap. Any task environment should log enough to re-grade
without re-running.

**Grader strictness is a policy decision you didn't know you made.** Every one of those fixes was a judgment call:
is a duplicate escalation wrong? Does "include the order ID in the summary" mean the summary text or the record?
Each choice moves a model's score. Exact-match grading is necessary but not neutral, and the choices need to be
written down next to the results.

**Policy lines that duplicate a structured field fail models in opposite ways.** The rule "the summary must
include the order ID" exists so a human can find the order. Haiku satisfied the text and skipped the field;
Sonnet filled the field and skipped the text. Sonnet's two "real" failures are this. A rule should either be
enforced by the tool schema (make `order_id` required) or stated as an outcome ("the escalation must identify the
order"), not both.

**The most realistic failure was not looking, not misreading.** Haiku's real miss: it took the customer ID from
the order record, verified, refunded, and never fetched the profile showing four refunds in 30 days. That's the
failure mode that matters for real deployments, where the deciding fact sits in a record the agent has no
obvious reason to open. Tasks that hide the deciding fact one lookup away are more discriminating than tasks that
test whether the agent knows the rule.

**A clean one-page policy is too easy for current models.** In the first round, both agents verified, chose refund versus credit,
respected caps, refused politely, escalated correctly and did nothing when nothing was right, in nearly every run.
To separate models, a task needs things this weekend version lacks: a longer policy with exceptions that
interact, more tools with overlapping uses, longer conversations, facts that contradict each other across systems,
and customers who are wrong rather than merely vague.

**The simulator has tells that a judge model misses.** The cheap simulator mostly followed its reveal rules (the
allergy only after the refund, the wrong suite number before the right one). But it also:

- thanked itself by its own name ("Thanks, Priya"), in 5 of the first 78 runs (8 of the final 150) and across both
  agents, apparently after the agent used that name;
- repeated its own instructions back ("I don't know the late-delivery policy");
- kept chatting after its goal was met, asking the agent to reconfirm things.

The judge model caught none of the first two. It raised two flags, one right and one wrong. Simple pattern rules,
written after reading transcripts, caught more. Simulator QA needs a person reading a sample of transcripts; an LLM
judge alone isn't enough.

**Cost estimates from first principles were 4–6× high.** Conversations were about half as long as we assumed,
and caching removed most of the input cost. The useful estimate is the observed cost per run from a small pilot,
so the tool now reports that. A full 39-run pass cost $0.07 with Haiku as the agent and $0.81 with Sonnet. At these
prices the expensive part of a benchmark like this is the human time spent reading transcripts, not the tokens.

## 6. Building a harder version (v2)

v2 added the levers that v1 lacked:

- a courier event log that contradicts the order record, and a written rule that the log wins;
- a payment record with promo discounts and automatic refunds;
- support-ticket history with earlier promises;
- Plus membership with higher limits, and a fraud review that overrides everything;
- customers who are wrong (wrong order number, an item already refunded, a failed delivery that was their fault);
- three issues in one chat.

**The first v2 run looked hard, and most of it was us again.** Haiku scored 64% and Sonnet 75%. Reading all 22
failures:

- **12 were escalations the customer had asked for.** When the simulated customer was told "no", it often asked for
  someone else to look at it ("can you pass my request along to someone who can?"). The policy says to escalate
  when a customer asks for a person, but each task's expected state had no escalation. Whether the simulator asks
  varies from run to run, so this escalation now has to be allowed, but not required, in every task. In a
  multi-turn simulation, any policy rule triggered by something the customer says has to be handled in every task,
  not just the ones written around it.
- **4 were escalations the policy never asked for and never forbade.** Haiku escalated "for review" whenever a
  customer was unhappy. The draft policy listed when to escalate but never said "only then". The policy was fixed
  and v2 re-run.
- **The rest were mostly real agent mistakes.** The re-run turned up one more benchmark bug: a customer said "yes,
  go ahead with the $12 refund and the $3 credit" and ended the chat in the same message, and the harness stopped
  before the agent could act. The agent now always answers the customer's last message.

**After the fixes, most of v2's new difficulty didn't bite.** Both models read the courier log over the order record
(a false "delivered" stamp, a "preparing" status on an order already picked up), caught the customer quoting last
week's order number, found the automatic refund, honoured the earlier promise at the recorded $6.50 rather than the
remembered $10, and refused to compensate a failed delivery that was the customer's fault. All of these passed every
run in the final round. When the policy names the record to check (the courier log, the payment record, the ticket
history), current models check it.

**What separated the models was combining rules.** Sonnet scored 100%, Haiku 89%, and Haiku's losses were the two
tasks that need rules combined:

- **A two-part rule.** On a promo order, a missing item is refunded to the card minus its share of the discount, and
  the discount share goes back as credit. Haiku computed the $12.00 card refund correctly in every failing run and
  never issued the $3.00 credit.
- **Rules that override each other, where one depends on a record nobody pointed at.** Wrong item normally means
  refund; getting sick means a food-safety escalation; three refunds in 30 days means a fraud review and no money at
  all, Plus member or not. Haiku went 0 of 3 in the final run.

**The fraud misses were all "not looking".** Across the three v2 rounds, in every Haiku run that refunded despite
the fraud rule (3 runs), it had never opened the customer profile that shows `refunds_last_30d`. In every run where
it opened the profile (6 runs), it applied the fraud review. That's the same failure as Haiku's only v1 miss (T11).
The policy names a source of truth for delivery, payment and history, but not for the refund count. That count sits
on a profile the agent has no particular reason to fetch once it has the order. The agent doesn't misread the rule;
it never sees the fact the rule depends on. Tasks where the deciding fact sits in a record the agent wouldn't
naturally open are the most discriminating ones we found, and the closest to how real deployments fail.

To build a benchmark that separates models, write tasks where two or three rules apply at once and one cancels part
of another, and put the deciding fact for one of them in a record the agent has no obvious reason to open. Messy
data and difficult customers matter less.

**Three trials is too few.** Two complete runs of the same model on the same suite differed by 3 to 8 points, and a
single task went from 3/3 in one run to 0/3 in the next (Haiku V09). The order of the two models flipped between v1
and v2. Before claiming one model is more reliable than another on a task, run k ≥ 5, and look at pooled per-task
counts, not one run's pass^3.

**Every fix has to be re-checked against every earlier run.** Each grader change was re-applied to all saved runs
(`supportsim regrade`), and each policy or harness change meant re-running. The total for ten complete runs was
$5.00, so re-running was cheap. The time went into reading transcripts to decide whether each failure was the model
or the benchmark. That reading, not compute, is the real cost of a trustworthy environment, and it's the part that
is hardest to hand off.

## 7. Trying to make the strongest model fail (v3)

v3 aimed for tasks Opus 5.5 fails 20 to 60% of the time, for real reasons. It didn't get there: Haiku passed 13 of
15 core tasks, and Sonnet and Opus passed everything, including six long "scale" tasks that Opus ran 5 times each.
Numbers are in [RESULTS_V3.md](RESULTS_V3.md).

**The v2 lever stopped working.** The most discriminating v2 tasks hid the deciding fact in a record the agent had
no obvious reason to open. Opus defeats that by opening almost every record before deciding anything: profile,
account activity, payment, tickets, delivery events, restaurant. A task that tests "did you look?" can't separate
agents that always look. Haiku still sometimes acts first and looks later (X10), so the lever still separates
smaller models.

**Volume didn't bite either.** Five issues in one chat, a running credit limit, a 9-line promo order, a 13-entry
refund history and chained cancel and replace actions: Opus went 30/30. Careful bookkeeping over a 15-turn chat is
not where it fails.

**Every apparent Opus failure was ours,** for the third suite running. Two runs failed:

- the simulated customer invented a missing item that wasn't in its facts;
- a policy sentence ("credits already received, for any problem") literally covered credit issued earlier in the
  same chat, and Opus applied it literally.

The better the agent, the more its "failures" are really tests of the benchmark. A strong model is also a good
detector of ambiguous policy: it finds the reading the author didn't intend and follows it consistently.

**What made a task genuinely hard versus artificially hard.**

- *Genuinely hard,* and it separated Haiku:
  - acting before looking when a customer pushes for speed;
  - applying only half of a rule that has two parts.

  These are failures a careful human agent would also be warned about.
- *Artificially hard:* anything that relies on ambiguous wording, on the simulator behaving off-script, or on a
  rule the agent has no way to find. Those produce failures, but the failures measure the benchmark.
- *Not hard at all, for current frontier models:*
  - longer chats and more records;
  - UTC conversion and time windows;
  - limits that add up;
  - precedence between rules, when the policy states it clearly.

**The designer's blind spot.** These tasks were designed by the same model family they were testing. Every task
started from a rule that could be stated clearly and a reference solution that could be written down, which is
exactly what makes it solvable by the same kind of reasoning. Finding tasks that genuinely trip a frontier model
probably needs inputs the designer doesn't generate:

- real support transcripts and real, messy policies;
- people who have watched agents fail in production;
- generating many variants and keeping the ones models fail.

That's the strongest argument we found for task-building as a service: the hard part isn't the harness, it's the
source material.
