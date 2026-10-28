# Results: v3food (food-delivery v3)

v3 set out to build tasks that the strongest model fails for real reasons: a target of Opus 5.5 passing 20 to 60%.
**It didn't get there.** Haiku 5.5 fails a little, and Sonnet 5.5 and Opus 5.5 pass everything. Every apparent Opus
failure turned out to be a benchmark bug. Design notes are in [V3_FOOD_DELIVERY_DRAFT.md](V3_FOOD_DELIVERY_DRAFT.md); what we learned is in
[LESSONS.md](LESSONS.md) section 7.

Runs were on 2026-10-27, with agents at `medium` effort. The simulated customer and the leak judge were
`claude-haiku-5-5` in every run. Total v3 spend was **$8.47**.

## The suite

- **21 tasks, `tasks/v3food/X01`–`X22`.** X08 was merged into X07 during design.
- **Policy:** `world/v3food/policy.md`, 13 sections.
- **Tools:** 13. v3 adds `get_restaurant`, `get_account_activity` and `create_replacement_order`.
- **Grader self-test:** 21 reference solutions that must pass and 82 known-wrong solutions that must fail. Each
  wrong solution was checked to fail on the check it targets.

There are two groups of tasks:

- **Core (X01–X16):** designed around the v2 lessons. The deciding fact sits in a record the agent has to think to
  open; rules combine and override each other; plus time windows, UTC courier logs, pressure, and cases where the
  right answer is to escalate or decline.
- **Scale (X17–X22):** hard by volume rather than by a single trick:
  - 4 to 5 issues in one chat
  - running credit limits
  - a 9-line order with a promo discount and items already refunded
  - a 13-entry refund history
  - chained cancel and replace actions

## Results

| Suite | Model | Trials per task | Passed | pass^1 | 95% CI (Wilson) | pass^5 |
|---|---|---|---|---|---|---|
| Core X01–X16 | Haiku 5.5 | 1 | 13/15 | 87% | 62–96% | n/a |
| Core X01–X16 | Sonnet 5.5 | 1 | 15/15 | 100% | 80–100% | n/a |
| Core X01–X16 | Opus 5.5 | 1 | 15/15 | 100% | 80–100% | n/a |
| Scale X17–X22 | Opus 5.5 | 5 | 30/30 | 100% | 89–100% | 100% |

Scale tasks were run only with Opus, because the question was whether anything trips the strongest model. The
X18 and X21 numbers come from a re-run after fixing two benchmark bugs (below); the first run scored 28/30. One
trial per core task is enough to see that Sonnet and Opus are at the ceiling, but not to rank them.

## Failure taxonomy

Every failing run was read in full and classified.

| Category | Count | Runs |
|---|---|---|
| Missed record lookup (acted before looking) | 1 | Haiku X10 |
| Wrong rule combination | 1 | Haiku X12 |
| Simulator problem | 1 | Opus X18, first run |
| Benchmark bug (ambiguous policy) | 1 | Opus X21, first run |
| Arithmetic error, ignored limit, skipped verification, gave in to pressure, wrong action order, failed to escalate | 0 | none |

So there were 2 real model failures, both Haiku, and 2 benchmark failures, both in Opus runs and both fixed.

**Simulator flags:** 10 of 85 runs. 9 came from the judge model ("revealed hidden info unprompted") and 1 was a
broken character. None of them caused a failure.

## Four failures, annotated

**1. Haiku, X10: refunded a likely account takeover.**
- **Setup:** the caller verified with name and phone, and `verify_identity` returned `verified: true`.
- **What Haiku did:** it refunded the $12 burger straight away.
- **The deciding fact:** account activity showed the phone had been changed 3 hours earlier from a new device in
  Phoenix, after a password reset. Haiku only opened it four turns later, after the customer happened to mention the
  change. It then escalated `account_security`, telling the customer "the new number shouldn't have been used to
  verify you", but the refund had already gone out.
- **Why it failed:** acting before looking. It's the same pattern as Haiku's v1 and v2 misses.

**2. Haiku, X12: half of a two-part rule.** On a $60 promo order, Haiku:
- correctly computed the lemonade's card refund as $3.00 ($4 − $15 × 4/60);
- correctly credited the grain bowl at $21.60;
- never issued the $1.00 promo-share credit that the same policy sentence requires.

Expected credits were $22.60; actual were $21.60. It's the same miss as Haiku on v2's V06.

**3. Opus, X18 (first run): the customer invented an item.**
- **What happened:** after Opus asked the office manager to count the chicken tacos, the simulated customer replied
  "only 5 of the 6", which isn't in its facts.
- **What Opus did:** refunded the extra taco with the correct promo split ($3.60 to the card and $0.40 credit).
- **The bug:** the scenario never said what *did* arrive, so the simulator filled the gap.
- **Fix:** the facts now state that everything else arrived in full.

**4. Opus, X21 (first run): a literal reading of an ambiguous rule.** Opus issued a $5 late credit on an order,
then reduced the same order's missing-item credit by that $5. The policy said: "If an order already received support
credits or refunds, for any problem, reduce anything you now owe on that order." I meant earlier contacts, but the
text covers credit issued minutes earlier in the same chat, and Opus applied it literally. The fix limits the rule
to compensation from earlier contacts. Runs made before the change were checked, and this was the only one whose
outcome depended on the old wording.

## Cost

| Run | Runs | Spend |
|---|---|---|
| Opus, core, k=1 | 15 | $1.30 |
| Haiku, core, k=1 | 15 | $0.05 |
| Sonnet, core, k=1 | 15 | $0.58 |
| Opus, scale, k=5 | 30 | $4.74 |
| Opus, X18 and X21 re-run, k=5 | 10 | $1.80 |
| **Total** | **85** | **$8.47** |

Opus cost about $0.09 per run on the core tasks and $0.16 to $0.18 per run on the scale tasks.

## Run folders

- **Core:** `results/20261027-175421_claude-opus-5-5`, `results/20261027-181238_claude-haiku-5-5` and
  `results/20261027-181415_claude-sonnet-5-5`.
- **Scale:** `results/20261027-182222_claude-opus-5-5`. Its X18 and X21 runs are superseded by
  `results/20261027-182949_claude-opus-5-5`.

Each folder has a `view.html`. The demo pages are in `demo/`.
