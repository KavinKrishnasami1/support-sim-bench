# Results

Run on 2026-10-26. 13 tasks × 3 trials per agent. The simulated customer and the leak judge were both
`claude-haiku-5-5` at low effort; the agents ran at `medium` effort. Total spend was **$0.89**: Haiku $0.07, Sonnet
$0.81, plus a $0.001 smoke test. The cap was $15.

| Task | Haiku 5.5 passed | Haiku pass^3 | Sonnet 5.5 passed | Sonnet pass^3 |
|---|---|---|---|---|
| T01 late delivery credit | 3/3 | 100% | 3/3 | 100% |
| T02 missing item refund | 3/3 | 100% | 3/3 | 100% |
| T03 two missing items, credit preference | 3/3 | 100% | 3/3 | 100% |
| T04 wrong item, customer wants full refund | 3/3 | 100% | 3/3 | 100% |
| T05 whole order missing, over limit | 3/3 | 100% | 3/3 | 100% |
| T06 address change, corrected suite | 3/3 | 100% | 3/3 | 100% |
| T07 address change after pickup | 3/3 | 100% | 3/3 | 100% |
| T08 very late, $15 cap vs $40 demand | 3/3 | 100% | 3/3 | 100% |
| T09 unrecognized charge | 3/3 | 100% | 3/3 | 100% |
| T10 wrong item, allergy revealed late | 3/3 | 100% | **1/3** | **0%** |
| T11 small claim, frequent refunder | **2/3** | **0%** | 3/3 | 100% |
| T12 caller isn't the account holder | 3/3 | 100% | 3/3 | 100% |
| T13 late and preparing, cancel | 3/3 | 100% | 3/3 | 100% |
| **All tasks** | **97% pass^1** | **92%** | **95% pass^1** | **92%** |

pass^1 is the share of all runs that passed. pass^3 is the share of tasks passed on all three trials, averaged
over tasks.

## What the numbers say

**Both models are near the ceiling, so in this form the benchmark is too easy to separate them.** A one-page
policy, seven tools and four- to five-turn conversations aren't hard for current models. Every verification,
refund-versus-credit choice, cap, escalation trigger and refusal was handled correctly in nearly every run. That
includes T12, where the right answer is to do nothing for a polite caller, and T08, where the customer pushes for
$40 against a $15 cap. The reliability gap the benchmark is meant to expose shows up only on two tasks, each in a
different model.

**The three real failures:**

- **Haiku, T11 (1 of 3 runs): it never looked.** It took the customer ID from the order record, verified the
  caller and refunded the $6.75 smoothie. It never called `get_customer`, so it never saw the
  `refunds_last_30d = 4` that should have sent the case to fraud review. It didn't misapply the policy; it skipped
  gathering the one fact the policy depended on.
- **Sonnet, T10 (2 of 3 runs): it broke a written rule.** The policy says "every escalation summary must include
  the order ID". Sonnet put `O-5110` in the escalation's `order_id` field but not in the summary text. Haiku did the
  opposite in 8 runs: it wrote the order ID in the summary and left the field empty, which satisfies the rule as
  written. The rule exists so a human can find the order, and both forms achieve that. A policy line that
  duplicates a structured field fails different models in opposite ways. We grade the policy as written; under a
  "spirit" reading Sonnet would be 39/39.

## Grader changes made after seeing the results

To be explicit, so these numbers aren't mistaken for tuning: the first pass graded Haiku at 77% and Sonnet at 90%.
Reading every failing transcript showed that 10 of the 13 failures were the benchmark's fault, not the agent's.
Three fixes were made. Both runs were then re-graded by replaying their logged tool calls (`supportsim regrade`),
with no new model calls:

| Fix | Why | Runs changed |
|---|---|---|
| An escalation's order can come from its summary when the optional `order_id` field is empty | The policy asks for the order ID in the summary, and the agent did that; the grader demanded the field | Haiku: 7 FAIL → PASS |
| T08 allows a `customer_request` escalation | The scripted opening "I need to talk to someone about my order" is reasonably read as asking for a person, which the policy says to escalate | Haiku: 1 FAIL → PASS (this run also needed the first fix) |
| Escalations are compared as a set | Sonnet filed a second "addendum" escalation for the same order and reason when the customer added details; the case is still escalated once, correctly | Sonnet: 2 FAIL → PASS |

`supportsim check` (13 oracles pass, 38 known mistakes fail) still passes after all three changes.

## The simulated customer

The reveal rules mostly worked. In T10 the allergy came up only after the refund, as scripted. In T06 the wrong
suite number came first and the correction followed. In T03 the second missing item came up only after the agent
asked. But the simulator had two tells that recur across runs, which neither the original rules nor the judge
caught. Both are now rule checks:

| Problem | Where | Runs |
|---|---|---|
| Thanking itself by its own name ("Thanks, Priya") after the agent used it | T03 (both agents), T10 | 6 messages in 5 runs |
| Repeating its own instructions ("I don't know the late-delivery policy") | T06 | 2 runs |
| Volunteering a detail its reveal rules held back | T11 (Sonnet run, judge) | 1 run |

The judge model raised 2 flags. One was right (T11). One was wrong (T03: the agent had asked, so the detail was
not volunteered). None of the flagged runs changed a pass or a fail, so no run was excluded.

## Cost

| | Haiku 5.5 agent | Sonnet 5.5 agent |
|---|---|---|
| Actual, 39 runs | $0.07 | $0.81 |
| Pre-run estimate, likely with caching | $0.33 | $5.06 |
| Pre-run estimate, no caching | $0.58 | $10.08 |
| Median per run | $0.0015 | $0.019 |
| Average customer turns | 4.8 | 4.7 |

The estimate was 4–6× too high. Conversations were about half as long as assumed, and prompt caching cut most of the
input cost. `supportsim estimate` now also shows the actual per-run cost of earlier runs with the same models.

## Reproduce

```bash
uv run supportsim run -k 3 --agent-model claude-haiku-5-5 --max-cost 2
uv run supportsim run -k 3 --agent-model claude-sonnet-5-5 --max-cost 12
uv run supportsim compare results/<haiku dir> results/<sonnet dir>
```

The full transcripts are in `results/20261026-170700_claude-haiku-5-5/view.html` and
`results/20261026-171043_claude-sonnet-5-5/view.html`.
