from supportsim.providers import ScriptedProvider
from supportsim.report import pass_hat_k
from supportsim.runner import run_episode
from supportsim.simuser import STOP_TOKEN
from supportsim.tasks import check_task, load_tasks

T02 = next(t for t in load_tasks(["T02"]))


def test_every_oracle_passes_and_every_mistake_fails():
    for suite in ("v1", "v2", "v3"):
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


def test_v3_authorized_user_and_replacement_order():
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    w = load_world(suite="v3")
    r, err = call_tool(w, "verify_identity", {"customer_id": "E309", "full_name": "Ken Tanaka",
                                              "email": "ken.tanaka@inbox.example"})
    assert not err and r["role"] == "authorized_user"
    r, err = call_tool(w, "create_replacement_order", {"order_id": "K-8701", "item_ids": ["K-8701-1"]})
    assert err  # the original must be marked not_delivered first
    call_tool(w, "update_order", {"order_id": "K-8701", "status": "not_delivered"})
    r, err = call_tool(w, "create_replacement_order", {"order_id": "K-8701", "item_ids": ["K-8701-1"]})
    assert not err and r["charge"] == 0.0


def test_v1_and_v2_tools_unchanged_by_v3():
    from supportsim.tools import call_tool, tool_specs
    from supportsim.world import load_world

    assert "get_restaurant" not in {t["name"] for t in tool_specs("v2")}
    w = load_world(suite="v2")
    r, _ = call_tool(w, "verify_identity", {"customer_id": "D201", "full_name": "Aisha Rahman",
                                            "email": "aisha.rahman@inbox.example"})
    assert r == {"verified": True, "customer_id": "D201"}
    r, err = call_tool(w, "update_order", {"order_id": "Q-7102", "status": "not_delivered"})
    assert err


def test_demo_pages_are_static(tmp_path):
    import glob
    from pathlib import Path

    from supportsim.demo import build

    runs = sorted(glob.glob("results/2026*/runs/X12_trial0.json"))[:2]
    dirs = sorted({Path(r).parent.parent for r in runs})
    for f in build([(Path(r), None) for r in runs], dirs, tmp_path):
        text = f.read_text()
        assert "<script" not in text and "http://" not in text and "https://" not in text
