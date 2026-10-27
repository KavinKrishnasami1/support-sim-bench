# support-sim-bench

A small multi-turn benchmark for customer-support agents, in the spirit of tau-bench (our own code). An agent
handles food-delivery support chats: late orders, missing and wrong items, refunds versus credits, address changes,
cancellations and escalations. A model plays the customer from a hidden scenario. The agent has tools that read
and write a small database and a written policy it must follow. Each run is graded on the database it leaves
behind and the actions it took, never on its wording.

Two suites, each task run k times and reported as pass rate and pass^k (the chance all k runs succeed):

- **v1**: 13 tasks, a one-page policy, 7 tools, single-issue chats.
- **v2**: 12 harder tasks, a longer policy and 10 tools. Records conflict (a courier event log versus the order
  record), there are promo splits, earlier promises in ticket history, Plus membership limits, a fraud review that
  overrides everything, customers who are wrong, and several issues in one chat.

Current results are in [RESULTS.md](RESULTS.md); what we learned building it is in [LESSONS.md](LESSONS.md).

## Quick start

```bash
uv sync
cp .env.example .env                    # then put ANTHROPIC_API_KEY=... in .env (gitignored)

uv run supportsim check [--suite v2]    # replays every task's oracle and known mistakes through the grader (free)
uv run supportsim estimate -k 3         # estimated cost, no API calls
uv run supportsim run -k 3 --max-cost 10                              # default agent: claude-opus-5-5
uv run supportsim run -k 3 --max-cost 2 --agent-model claude-haiku-5-5 --tasks T01,T05
uv run supportsim run --suite v2 -k 3 --max-cost 4 --agent-model claude-sonnet-5-5
uv run supportsim regrade results/<run folder>   # re-grade saved runs with the current grader, no model calls
open results/<run folder>/view.html     # every transcript, tool call and grader check
```

`run` prints a cost estimate and asks for confirmation before any API call. `--max-cost` is required: once total
spend reaches it, no new API call starts and the remaining runs are skipped.

## How it works

| Piece | Where | What it does |
|---|---|---|
| World | `world/base.json`, `world/v2/base.json` (built by `scripts/build_world*.py`) | Customers, restaurants, orders (items, prices, fees, status, timestamps), payments, credits and escalations. Loaded fresh for every run, with a fixed "now" so lateness and 48-hour windows are deterministic. |
| Policy | `world/policy.md`, `world/v2/policy.md` | The rules the agent must follow: identity verification, late-delivery credits, missing/wrong items (refund or credit +20%), escalation triggers, address changes, cancellations, a $25 credit cap. Given to the agent verbatim. |
| Tools | `src/supportsim/tools.py` | `get_customer`, `verify_identity`, `get_order`, `issue_refund`, `issue_credit`, `update_order`, `escalate_to_human`; v2 adds `get_delivery_events`, `get_payment`, `get_ticket_history`. They enforce data integrity only (no refunding more than was paid), not policy, so policy mistakes reach the grader instead of being blocked. |
| Simulated customer | `src/supportsim/simuser.py` | A cheap model (default `claude-haiku-5-5`) given a persona, a situation, a goal, facts, reveal rules and an end condition. It shares facts only when asked, never states the policy or the remedy, and ends the chat with a stop token. It sees the agent's messages, never tool calls. |
| Tasks | `tasks/T*.json`, `tasks/v2/V*.json` | Scenario, expected effects, the "oracle" (what a perfect agent does) and named mistakes. Sources and licenses in [PROVENANCE.md](PROVENANCE.md). |
| Grader | `src/supportsim/grader.py` | Pass only if every check passes (below). |
| Simulator flags | `src/supportsim/flags.py` | Flags runs where the customer broke character or leaked the answer: rule-based checks plus an optional judge model (`--judge-model`, `--no-judge`). Flags don't change pass/fail; they mark runs to read or exclude. |
| Harness | `src/supportsim/runner.py`, `cli.py` | Runs tasks × k with a thread pool, tracks cost per call, enforces the cap, writes one JSON per run. |
| Viewer | `src/supportsim/viewer.py` | `results/<run>/view.html`: summary table, filters for failed and flagged runs, and each full conversation with tool calls, grader checks and flags. `supportsim show <run json>` prints one in the terminal. |

## Grading

A run passes only if all of these hold:

- **State.** The run's effects match the task's expected effects exactly: refund total per order, credit total
  per customer, changed order fields (status, address) and escalations (order and reason). Amounts are matched to
  the cent. Addresses are matched on required and forbidden words, so "Suite 310" passes and "Suite 300" fails.
  Some tasks allow an extra escalation, such as a customer-requested one.
- **Verify first.** Every write (refund, credit, order update, escalation) came after a successful
  `verify_identity` for that customer.
- **Escalation summaries name the order.**
- **Credit cap.** At most $25 of credit in the conversation, across all `issue_credit` calls.
- **Task-specific** required or forbidden tool calls, where a task defines them.

Runs that end in an API error, the cost cap or a simulator refusal are not graded and are reported separately.

`supportsim check` replays each task's oracle (must pass) and each named mistake (must fail), such as refunding the
whole order, skipping verification, giving in to a $40 demand, or refunding $60 and escalating the rest. There are
38 such mistakes in v1 and 31 in v2; that check is the grader's own test suite. An escalation because the customer
asked for a person is always allowed (never required), since the policy requires it whenever the customer asks.

## pass^k

For a task with n graded runs and c passes, pass^k = C(c, k) / C(n, k): the probability that k runs drawn without
replacement all pass. With n = k it is simply "passed every time". The overall number is the mean across tasks.
pass^1 equals the pass rate; pass^3 is what tells you whether an agent is reliable, not just capable.

## v1 tasks

| ID | Scenario | What makes it hard |
|---|---|---|
| T01 | Late delivery (25 min) | Customer wants a card refund; policy allows only credit, equal to the delivery fee |
| T02 | Missing item | Customer only knows his phone, not the email; an older order has the same item |
| T03 | Two missing items | Second item mentioned late; customer prefers credit (+20%) but only says so when asked |
| T04 | Wrong item | Customer demands a full refund; only the wrong item qualifies |
| T05 | Whole order never arrived | Full refund owed but over the $60 limit: escalate, refund nothing |
| T06 | Address change while preparing | Customer gives the wrong suite first, then corrects it |
| T07 | Address change after pickup | Nothing can be done; the right outcome is no change at all |
| T08 | 80 minutes late | 20% would be $18.40 but the cap is $15; customer demands $40 |
| T09 | Unrecognized charge | No order number given; must escalate, not refund |
| T10 | Wrong item, allergy revealed late | Needs a refund and a food-safety escalation |
| T11 | Small missing item | 4 refunds in 30 days: escalate for review, refund nothing |
| T12 | Caller isn't the account holder | Can't verify; correct outcome is no action |
| T13 | Late and still preparing | Status check becomes a cancellation: cancel plus full-total refund, no late credit |

## v2 tasks

| ID | Scenario | What makes it hard |
|---|---|---|
| V01 | Plus member, three issues in one chat | Issues surface one after another across two orders |
| V02 | Late burgers | Order record says on time; the courier log shows a false "delivered" and a 47-minute-late handoff |
| V03 | Missing smoothie | It was already refunded automatically; the customer is wrong |
| V04 | Missing elote | The customer quotes last week's order number |
| V05 | "Never arrived" | Photo proof of delivery: escalate as a dispute, don't refund |
| V06 | Missing pho on a promo order | Card refund minus the promo share, plus the share as credit |
| V07 | Chasing a promised credit | Ticket history says $6.50; the customer remembers $10 |
| V08 | Late order | Already compensated in an earlier chat |
| V09 | Wrong item, got sick, frequent refunder, Plus | Food-safety and fraud-review escalations, no refund |
| V10 | "Never arrived" | The courier couldn't reach the customer |
| V11 | Cancel request | Status says preparing; the courier log says picked up |
| V12 | Whole order lost, $87.55, Plus | Under the Plus limit, so refund directly; no goodwill extra |

## Using another model

Any model can be the agent or the customer. Write a `Provider` (see `src/supportsim/providers.py`):
`start(system, tools)` returns a conversation with `send_user(text)` and `send_tool_results(results)`, each
returning a `Turn(text, tool_calls, stop_reason, usage)`. Add the model's prices to `PRICES` so the cost cap works,
then run with `--agent-provider my_module:MyProvider --agent-model my-model`. `ScriptedProvider` is a minimal
example and powers the tests.

## Adding a task

Copy a file in `tasks/`. Fill in the customer scenario, `expected` effects, an `oracle` action list and at least two
`mistakes`, then run `uv run supportsim check`. If a mistake passes, the grader has a hole; fix it or tighten the
expected effects. If you change the world, edit `scripts/build_world.py` and rerun it.

## Files

```
world/            base.json, policy.md (v1); v2/base.json, v2/policy.md
tasks/            T01..T13 (v1); v2/V01..V12
src/supportsim/   world, tools, grader, simuser, flags, providers, runner, report, viewer, cli
scripts/          build_world.py, build_world_v2.py, download_abcd.sh, show_source.py, write_provenance.py
results/          one folder per run: config.json, runs/*.json, summary.json, view.html; superseded/ holds
                  runs from before the fixes listed in RESULTS.md
RESULTS.md        results from running two models on both suites
LESSONS.md        what was hard: simulator realism, grader loopholes, ambiguous policy
```
