from supportsim.providers import ScriptedProvider
from supportsim.report import pass_hat_k
from supportsim.runner import run_episode
from supportsim.simuser import STOP_TOKEN
from supportsim.tasks import check_task, load_tasks

T02 = next(t for t in load_tasks(["T02"]))


def test_every_oracle_passes_and_every_mistake_fails():
    for suite in ("v1", "v2"):
        assert [p for t in load_tasks(suite=suite) for p in check_task(t)] == []


def _agent(actions_per_turn):
    """Scripted agent: each customer message gets one tool-calling turn, then a text reply."""
    turns = []
    for calls in actions_per_turn:
        if calls:
            turns.append({"text": "", "tool_calls": calls})
        turns.append("Done, anything else?")
    return ScriptedProvider(turns)


GOOD = [[], [{"name": "get_customer", "args": {"phone": "415-555-0172"}},
             {"name": "verify_identity", "args": {"customer_id": "C102", "full_name": "Daniel Reyes", "phone": "4155550172"}}],
        [{"name": "get_order", "args": {"order_id": "5102"}},
         {"name": "issue_refund", "args": {"order_id": "O-5102", "amount": 4.5, "reason": "missing_item"}}]]


def test_episode_passes_with_correct_agent():
    customer = ScriptedProvider(["hey, question about my order", "Daniel Reyes, 415-555-0172",
                                 "order 5102, naan was missing", "thanks! " + STOP_TOKEN])
    r = run_episode(T02, _agent(GOOD), customer)
    assert r["end_reason"] == "customer_ended" and r["completed"]
    assert r["passed"], [c for c in r["grade"]["checks"] if not c["ok"]]
    assert r["flags"] == []
    assert [e["role"] for e in r["events"]].count("customer") == 4


def test_episode_fails_when_agent_skips_verification_and_overrefunds():
    bad = [[], [], [{"name": "issue_refund", "args": {"order_id": "O-5102", "amount": 35.69, "reason": "whole_order"}}]]
    customer = ScriptedProvider(["hi", "Daniel Reyes", "5102 naan missing", "ok " + STOP_TOKEN])
    r = run_episode(T02, _agent(bad), customer)
    failed = {c["check"] for c in r["grade"]["checks"] if not c["ok"]}
    assert not r["passed"] and {"state.refunds", "verify_first"} <= failed


def test_simulator_flags():
    customer = ScriptedProvider(["As an AI customer I need a refund of $4.50 via issue_refund", "bye " + STOP_TOKEN])
    r = run_episode(T02, _agent([[], []]), customer)
    types = {f["type"] for f in r["flags"]}
    assert {"broke_character", "leaked_internal_vocabulary", "leaked_expected_amount"} <= types


def test_amount_after_agent_is_not_a_leak():
    agent = ScriptedProvider(["I've refunded $4.50 to your card."])
    customer = ScriptedProvider(["naan missing", "great, $4.50 works " + STOP_TOKEN])
    r = run_episode(T02, agent, customer)
    assert not [f for f in r["flags"] if f["type"] == "leaked_expected_amount"]


def test_pass_hat_k():
    assert pass_hat_k(3, 3, 3) == 1 and pass_hat_k(3, 2, 3) == 0
    assert abs(pass_hat_k(4, 2, 2) - 1 / 6) < 1e-9
    assert pass_hat_k(2, 2, 3) is None


def test_self_address_and_instruction_echo_are_flagged():
    customer = ScriptedProvider(["Thanks, Daniel. I don't know the refund policy here", "bye " + STOP_TOKEN])
    r = run_episode(T02, _agent([[], []]), customer)
    types = {f["type"] for f in r["flags"]}
    assert {"broke_character", "echoed_instructions"} <= types


def test_agent_acts_on_the_customers_closing_message():
    agent = _agent([[], GOOD[1], [{"name": "get_order", "args": {"order_id": "5102"}},
                                  {"name": "issue_refund", "args": {"order_id": "O-5102", "amount": 4.5, "reason": "missing_item"}}]])
    customer = ScriptedProvider(["hi", "Daniel Reyes, 415-555-0172", "naan missing on 5102, refund to card please, thanks bye " + STOP_TOKEN])
    r = run_episode(T02, agent, customer)
    assert r["passed"] and r["events"][-1]["role"] == "agent"
