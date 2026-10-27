# Results

Run on 2026-10-26 with two agent models, Claude Haiku 5.5 and Claude Sonnet 5.5, both at `medium` effort. Each was
run on both suites with 3 trials per task. The simulated customer and the leak judge were `claude-haiku-5-5`.
Every number below comes from the final runs in `results/2026102617345*`. Earlier runs, kept in
`results/superseded/`, are described at the end. Total API spend across everything, superseded runs included, was
**$5.00**.

## Headline

| Suite | What it is | Haiku 5.5 pass^1 | Haiku pass^3 | Sonnet 5.5 pass^1 | Sonnet pass^3 |
|---|---|---|---|---|---|
| **v1** (13 tasks) | One-page policy, 7 tools, single-issue chats | 100% | 100% | 92% | 85% |
| **v2** (12 tasks) | Longer policy, 10 tools, conflicting records, interacting rules, multi-issue chats | 89% | 83% | **100%** | **100%** |

pass^1 is the share of runs that passed. pass^3 is the share of tasks passed on all three trials, averaged over
tasks.

- **v2 separates the models; v1 doesn't.** On v2, Sonnet was perfect and Haiku failed the two tasks built around
  rules that must be combined. On v1, both are near the ceiling, and Sonnet's only losses come from one badly
  designed policy line.
- **Most of v2's new difficulty didn't bite.** In the final runs, both models handled every task where the answer depended on reading
  the courier log over the order record (V02, V11, V12) or catching a customer's wrong claim (V03, V04, V08, V10).
  What separated them was **combining rules**: a two-part refund (V06) and three rules that override each other
  (V09).
- **Three trials is not enough to rank close models.** The same model on the same suite moved 3 to 8 points between
  two complete runs (table at the end), and the order of the two models flipped between suites.

## Per task

**v2**

| Task | What makes it hard | Haiku | Sonnet |
|---|---|---|---|
| V01 | Plus member, three issues surfacing one after another, two orders | 3/3 | 3/3 |
| V02 | Order record says on time; courier log shows a false "delivered" and a 47-minute-late handoff | 3/3 | 3/3 |
| V03 | Customer reports a missing item that was already refunded automatically | 3/3 | 3/3 |
| V04 | Customer quotes last week's order number | 3/3 | 3/3 |
| V05 | "Never arrived", but the courier left a photo: dispute escalation, no refund | 3/3 | 3/3 |
| V06 | Missing item on a $10-promo order: $12.00 to the card plus $3.00 credit | **2/3** | 3/3 |
| V07 | Earlier agent promised $6.50 credit, never issued; customer remembers $10 | 3/3 | 3/3 |
| V08 | Late order already compensated in an earlier chat | 3/3 | 3/3 |
| V09 | Plus member, wrong item, got sick, 3 refunds in 30 days: two escalations, no money | **0/3** | 3/3 |
| V10 | "Never arrived", but the customer couldn't be reached | 3/3 | 3/3 |
| V11 | Status says preparing, but the courier picked it up: no cancellation | 3/3 | 3/3 |
| V12 | Plus member, whole order lost, $87.55: under the Plus $100 limit, so refund directly | 3/3 | 3/3 |

**v1:** Haiku passed all 39 runs. Sonnet passed 36. It failed T10 twice (put the order ID in the escalation's field
but not in its summary, as the v1 policy literally requires) and T04 once (escalated a wrong-burger complaint with
the reason `unrecognized_charge`).

## How the agents failed

- **Doing half of a two-part rule (Haiku, V06).** In every failing run Haiku computed the promo-adjusted card
  refund correctly ($15 − $10 × 15/50 = $12.00), then never issued the $3.00 promo-share credit the same sentence
  of the policy requires.
- **Not looking, then missing an override (Haiku, V09).** Three rules apply at once: a wrong item is normally
  refunded, illness needs a food-safety escalation, and three refunds in 30 days means a fraud review with no
  refund at all. In two runs Haiku refunded and escalated only for food safety. In both, it had never opened the
  customer profile that shows the refund count. In the third run it opened the profile and escalated for fraud, but
  missed food safety. Across all v2 rounds, every Haiku run that opened the profile applied the fraud review, and
  every run that refunded hadn't opened it. Sonnet got all three runs right.
- **A literal rule about where the order ID goes (Sonnet, v1 T10).** v1's policy asks for the order ID in the
  escalation summary. Sonnet usually puts it in the structured `order_id` field instead (4 of 6 runs across both rounds). v2's policy asks for the
  field, and Sonnet never fails it there.
- **A wrong escalation reason (Sonnet, v1 T04, once).**

## What changed during the runs

These numbers come after several fixes. Each was found by reading failing transcripts, and each is a bug in the
benchmark, not a change to help a model. All are in the git history.

| # | Change | Found because | Effect |
|---|---|---|---|
| 1 | An escalation's order can come from its summary when the optional `order_id` field is empty (v1) | 7 Haiku runs failed for doing exactly what the policy asks | Grader only; re-graded without new model calls |
| 2 | Escalations compared as a set, not a list | Sonnet filed an "addendum" escalation for the same case | Grader only |
| 3 | An escalation because the customer asked for a person is always allowed (never required) | Simulated customers who are told "no" often ask for someone else, and the policy says to escalate when they do; 13 of 13 such escalations followed a real ask | Grader only |
| 4 | v2 policy: "Do not escalate in any other situation" | Haiku escalated "for review" in cases the policy didn't cover, and the draft policy never said not to | Policy changed, so v2 was re-run |
| 5 | The agent always answers the customer's last message | A customer said "yes, go ahead with the $12 refund and the $3 credit" and ended the chat in the same message; the agent never got to act | Harness changed, so all four suites were re-run |

Before these fixes, the first v2 run scored Haiku 64% and Sonnet 75%. That looked like a hard benchmark, but more
than half of those failures came from fixes 3 to 5.

## Run-to-run variation

The same model on the same suite and tasks, comparing two complete runs. The earlier runs are re-graded with the
current grader; they predate fix 5, and the v2 ones also predate fix 4.

| Suite | Model | pass^1, earlier run | pass^1, final run |
|---|---|---|---|
| v1 | Haiku 5.5 | 97% | 100% |
| v1 | Sonnet 5.5 | 95% | 92% |
| v2 | Haiku 5.5 | 92% | 89% |
| v2 | Sonnet 5.5 | 97% | 100% |

Pooled over both runs, the tasks that ever failed are: Haiku V09 (3/6), Haiku V06 (2/6), Sonnet v1 T10 (2/6),
Haiku T11, Sonnet T04 and Sonnet V06 (5/6 each). Sonnet's V06 miss was the harness bug that fix 5 addressed. A
single 3-trial run can show a task at 0/3 that another run shows at 3/3 (Haiku V09). Use k ≥ 5 before treating a
per-task difference as real.

## The simulated customer

The final runs flagged 27 of 150 runs. The recurring problems:

- **It thanks itself by its own name** ("Thanks, Priya", "Thank you, Ruth"), usually right after the agent used
  that name. This happened in 8 runs across both suites and both agents.
- **It says a solution phrase before the agent does**, in 8 runs: "already refunded", "picked up", "review",
  "escalate". These are mostly customers guessing out loud, but they hand a weak agent the answer.
- **It volunteers details its reveal rules hold back**, according to the judge model, in 12 runs. These haven't
  been hand-checked; in the first v1 run, 1 of its 2 flags was wrong.

Three failed runs had flagged customers. In each, the flagged behaviour didn't cause the failure: in T10 the
customer said "escalate" first, but the agent failed on where it put the order ID. In two V09 runs the customer
mentioned being sick early, which makes the task easier, not harder.

## Cost

| | v1 Haiku | v1 Sonnet | v2 Haiku | v2 Sonnet |
|---|---|---|---|---|
| Final run | $0.08 | $0.91 | $0.09 | $0.98 |
| Per run (median) | ~$0.002 | ~$0.02 | ~$0.002 | ~$0.03 |
| Average customer turns | 4.7 | 4.7 | 4.5 | 4.5 |

The full history, ten complete runs plus a smoke test, cost $5.00.

## Reproduce

```bash
uv run supportsim run --suite v1 -k 3 --agent-model claude-haiku-5-5 --max-cost 1
uv run supportsim run --suite v2 -k 3 --agent-model claude-sonnet-5-5 --max-cost 4
uv run supportsim compare results/<dir a> results/<dir b>
uv run supportsim regrade results/<dir>      # re-grade saved runs with the current grader, no model calls
```

Transcripts: open `view.html` in any results folder.
