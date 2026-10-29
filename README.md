# support-sim-bench

Multi-turn evals for AI customer support and IT service desk agents, in the spirit of tau-bench (our own code).
- In each task, a model plays a customer or employee working from a hidden scenario.
- The agent has tools that read and write a small fictional world, plus a written policy it must follow.
- Grading checks **what the agent did**, never just what it said: the final state of the world, the order of its actions, their parameters, security rules, and whether its statements match its actions.

**Headline (v4real):** the newest suite is built from real public IT policies and real support-thread shapes. Opus 5.5 still passed **36/36** runs, with no security violations. Sonnet 5.5 passed **30/36** and Haiku 5.5 **21/36**.
- What separated the smaller models: a procedure that changes mid-chat, a requester asking for the wrong thing, and rules buried late in a long policy.
- What didn't: stale appendices and messy, cross-referenced documents.

## Suites

All results are from Claude agents at `medium` effort. The simulated user is `claude-haiku-5-5`. "k" is trials per task.

| Suite | What it tests | Tasks | Results |
|---|---|---|---|
| **v1** | Food-delivery support: one-page policy, 7 tools, single-issue chats | 13 | k=3, pass^1 (pass^3): Haiku 100% (100%), Sonnet 92% (85%) |
| **v2** | Longer policy, 10 tools, conflicting records, rules that combine and override, several issues per chat | 12 | k=3, pass^1 (pass^3): Haiku 89% (83%), Sonnet 100% (100%) |
| **v3food** | Food delivery aimed at the strongest models: deciding facts in records the agent must think to open, plus "scale" tasks (4–5 issues, a 13-entry refund history) | 21 (15 core + 6 scale) | Core, k=1: Haiku 13/15, Sonnet 15/15, Opus 15/15. Scale, k=5: Opus 30/30 |
| **v3** | IT service desk for a fictional 340-person company: access and approvals, delegation, nested groups, segregation of duties, licenses, MFA resets, impersonation. 18-section policy, 33 tools. Includes 3 long workflows (37–77 tool calls) | 19 (16 short + 3 long) | k=1: Haiku, Sonnet and Opus 16/16 on the short tasks; Haiku 3/3 on the workflows. 0 security violations |
| **v3kb** | The same 19 v3 tasks, but the policy lives in wiki articles next to superseded versions with looser rules | 19 | k=1: Haiku 14/19 (4 real failures, all from never opening the governing article), Opus 17/19 (0 real failures) |
| **v4real** | Policy wiki adapted from real public IT policies (US GSA, UK Ministry of Justice), request shapes from real public support threads. Also: tools that time out, a lagging directory, mid-chat changes | 12 (7 real-source + 5 synthetic) | k=3: Opus 36/36, Sonnet 30/36, Haiku 21/36 (3 Haiku runs had a security violation) |

- v4real has one policy ambiguity, which came from my own adaptation. Counted strictly, Opus scores 33/36 and Sonnet 27/36.
- One of Sonnet's 6 v4real failures was a simulator problem; the other 20 Sonnet and Haiku failures are genuine.
- Full write-ups: [RESULTS.md](RESULTS.md) (v1, v2), [RESULTS_V3_FOOD.md](RESULTS_V3_FOOD.md), [RESULTS_V3.md](RESULTS_V3.md) (v3, v3kb) and [RESULTS_V4.md](RESULTS_V4.md).

## How grading works

A run passes only if every check passes. In plain language:

- **Goal-based end state.** Whatever the user legitimately needed must be true at the end: the right refund to the cent, the right group, the right expiry. In the IT suites this is a minimum, not one scripted path. For example, any approver the policy accepts counts.
- **No extra changes.** Every change must be part of the goal. An unrequested MFA reset, or a grant to the wrong person or group, fails.
- **Order.** Verify identity before touching credentials. Get approval before granting access. Free a seat before assigning it.
- **Parameters.** The right person, group, product, expiry and destination. For example, a reset link must go to the contact on the HR record.
- **Say-do checks.** A model lists every claim the agent makes about its actions ("I've escalated this to Security"). Code then checks each claim against the tool log. Claiming something that never happened fails.
- **Error recovery.** If a needed write fails (tools can be made to time out), the agent must retry it or tell the user. A silent failure fails.
- **Security violations, reported as their own metric.** Examples: privileged access without approval, an MFA reset without verification, a segregation-of-duties conflict. Each call is judged when it's made, so a violation fails the run even if the agent undoes it later.
- **Grader self-test.** Every task has a reference solution that must pass and named wrong solutions that must fail. On the IT suites, 126 generated transcripts add cases like "claims an action it never took", "violation then undo" and "silent failure". `supportsim check` replays them all, with no model calls.

The IT suites also report a process score (0–1) next to pass/fail. It never decides pass/fail. Details: [GRADER_V2.md](GRADER_V2.md).

## Key lessons

Full notes are in [LESSONS.md](LESSONS.md).

- **Self-designed tasks didn't break Opus.** None of these caught it: hidden records, rules that override each other, 5-issue chats, nested groups, expired approvals or 77-call workflows. It opens every record and looks up the relevant policy before acting.
- **Real-source tasks separated Sonnet and Haiku, but not Opus.** Sonnet's 6 failures were all on real-source tasks (15/21 real vs 15/15 synthetic). With 3 trials that's suggestive, not conclusive.
- **Most first-run failures were ours, not the model's.**
  - v1: 10 of 13 first failures were benchmark bugs.
  - v3 short tasks: all 8 failures were simulator or benchmark problems.
  - v4real: of 52 first-run failures, 28 were grader false positives and 15 were on tasks rerun after environment fixes. None of Opus's 15 was a model failure.
  - Reading every failing transcript before counting it changed every headline.
- **AI-based checks need human review.** The say-do checker caught 1 genuine false statement. It also produced about 30 false positives before its matching rules matured, mostly from qualified denials like "not the admin account". Every say-do failure was read by hand.

## Limitations

- **Few trials per task.** Results are directional. Most suites ran k=1 or k=3, and between two complete runs the same model moved 3–8 points on the same suite.
- **One simulated-user model** (`claude-haiku-5-5`). It sometimes breaks character, leaks hints or disputes things it can't see. Flagged runs were read, but this remains a source of noise.
- **Adapted policies.** The v4real policy is my adaptation of public documents, not a live policy. Its one ambiguity came from that adaptation.
- **Small task counts** (12–21 per suite) and **one model family** tested.
- **Scripted personas.** The real-source tasks use the *shape* of real threads, rewritten into scripted personas, not real conversations.

## Quick start

```bash
uv sync
cp .env.example .env          # add ANTHROPIC_API_KEY (the only key needed; .env is gitignored)

uv run supportsim check --suite v4real            # grader self-test, no model calls
uv run supportsim run --suite v4real -k 3 --agent-model claude-sonnet-5-5 --max-cost 6
uv run supportsim view results/<run folder>       # or open results/<run folder>/view.html
uv run supportsim regrade results/<run folder>    # re-grade saved runs, no model calls
```

- Suites: `v1`, `v2`, `v3food`, `v3`, `v3kb`, `v4real`. Use `--tasks R01,R08` to pick tasks.
- The viewer shows every transcript, tool call and grader check.

**Other models.** Write a `Provider` (see `src/supportsim/providers.py`), add its prices to `PRICES`, and run with `--agent-provider my_module:MyProvider --agent-model my-model`.

## Data and sources

- **Everything in the worlds is fictional.** That covers every company (including "Quillmark Labs"), person, account, order and record. Email addresses use `.example` domains.
- **No real people's data is included.**
- **v1/v2:** customer behaviour was modelled on conversation shapes from the ABCD dataset (MIT). No text was copied. See [PROVENANCE.md](PROVENANCE.md).
- **v4real:**
  - Policies were adapted from public-domain US GSA guides and MIT-licensed UK Ministry of Justice guidance.
  - Request shapes came from public Wikimedia Phabricator and Server Fault threads (CC BY-SA). Only the shape was taken; no text, names or identifiers.
  - Every source, its license and its checksum are listed in [SOURCES.md](SOURCES.md).
- **Raw source files are not stored in the repo.** `scripts/download_abcd.sh` and `scripts/fetch_v4_sources.sh` fetch pinned, checksummed versions.
- **License:** MIT ([LICENSE](LICENSE)). Content adapted from the Ministry of Justice guidance keeps its own MIT notice, reproduced in each adapted wiki page. The GSA material is public domain.

## Layout

```
tasks/              v1 tasks; tasks/<suite>/ for the others (scenario, expected state, reference solution, named mistakes)
world/              v1 world and policy; world/<suite>/ for the others (v4real: world/v4real/wiki)
src/supportsim/     harness, simulated user, grader, viewer, CLI; itsd/ holds the IT suites' tools and grader v2
results/            one folder per run: config, per-run JSON, summary, view.html
demo/               static example run pages
```
