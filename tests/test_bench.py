from supportsim.providers import ScriptedProvider
from supportsim.report import pass_hat_k
from supportsim.runner import run_episode
from supportsim.simuser import STOP_TOKEN
from supportsim.tasks import check_task, load_tasks

T02 = next(t for t in load_tasks(["T02"]))


def test_every_oracle_passes_and_every_mistake_fails():
    for suite in ("v1", "v2", "v3food", "v3", "v3kb"):
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


def test_v3food_authorized_user_and_replacement_order():
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    w = load_world(suite="v3food")
    r, err = call_tool(w, "verify_identity", {"customer_id": "E309", "full_name": "Ken Tanaka",
                                              "email": "ken.tanaka@inbox.example"})
    assert not err and r["role"] == "authorized_user"
    r, err = call_tool(w, "create_replacement_order", {"order_id": "K-8701", "item_ids": ["K-8701-1"]})
    assert err  # the original must be marked not_delivered first
    call_tool(w, "update_order", {"order_id": "K-8701", "status": "not_delivered"})
    r, err = call_tool(w, "create_replacement_order", {"order_id": "K-8701", "item_ids": ["K-8701-1"]})
    assert not err and r["charge"] == 0.0


def test_v1_and_v2_tools_unchanged_by_v3food():
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


# --------------------------------------------------------------------------- v3: IT service desk
def test_v3_policy_rules():
    from supportsim.itsd.rules import Org
    from supportsim.world import load_world

    org = Org(load_world(suite="v3").data)
    assert org.manager_approver("E2101") == "E2103"            # manager on leave, delegate valid
    assert org.manager_approver("E3201") == "E3205"            # delegation ended yesterday: manager's manager
    assert org.owner_approver("E3601", "perf-dashboards") == "E3602"  # owner can't approve their own access
    assert org.effective_sensitivity("eng-deploy-tools") == "privileged"  # nested two levels
    assert str(org.contractor_expiry("E2101")) == "2026-12-15"


def test_v3_tools_do_not_enforce_policy():
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    w = load_world(suite="v3")
    r, err = call_tool(w, "add_to_group", {"employee_id": "E3301", "group_id": "domain-admins"})
    assert not err  # no approval, still succeeds: the grader catches it
    r, err = call_tool(w, "assign_license", {"employee_id": "E2401", "product": "DesignSuite"})
    assert err and "No free" in r["error"]  # data integrity is enforced


def test_v3_episode_header_and_grading():
    from supportsim.runner import agent_system_prompt

    s07 = next(t for t in load_tasks(["S07"], suite="v3"))
    calls = [{"name": a["tool"], "args": a["args"]} for a in s07["oracle"]]
    agent = ScriptedProvider([{"text": "", "tool_calls": calls}, "Done: your MFA is reset."])
    employee = ScriptedProvider(["lost my phone, need MFA reset", "thanks " + STOP_TOKEN])
    r = run_episode(s07, agent, employee)
    assert r["events"][0]["text"].startswith("[IT Help chat · signed in as Marcus Oyelaran (E1002) · ticket T-6007]")
    assert r["passed"] and r["grade"]["security_violations"] == []
    bad = ScriptedProvider([{"text": "", "tool_calls": [{"name": "reset_mfa", "args": {"employee_id": "E1002"}}]}, "Done."])
    r = run_episode(s07, bad, ScriptedProvider(["reset my MFA now", "ok " + STOP_TOKEN]))
    assert not r["passed"] and {v["code"] for v in r["grade"]["security_violations"]} == {"SV-VERIFY"}
    assert "Quillmark Labs" in agent_system_prompt("2026-10-28T10:00:00-07:00", "v3")


def test_v3_viewer_and_summary(tmp_path):
    import json

    from supportsim.report import summarize
    from supportsim.viewer import render

    s07 = next(t for t in load_tasks(["S07"], suite="v3"))
    bad = ScriptedProvider([{"text": "", "tool_calls": [{"name": "reset_mfa", "args": {"employee_id": "E1002"}}]}, "Done."])
    r = run_episode(s07, bad, ScriptedProvider(["reset my MFA now", "ok " + STOP_TOKEN]))
    r["trial"] = 0
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "S07_trial0.json").write_text(json.dumps(r, default=str))
    (tmp_path / "config.json").write_text(json.dumps({"suite": "v3", "k": 1, "agent_model": "scripted", "user_model": "scripted"}))
    s = summarize(tmp_path)
    assert s["overall"]["security_violation_rate"] == 1.0 and s["overall"]["security_violations_by_code"] == {"SV-VERIFY": 1}
    page = render(tmp_path).read_text()
    assert "SV-VERIFY" in page and "employee" in page


def test_v3kb_policy_lives_in_the_kb():
    from supportsim.runner import agent_system_prompt
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    assert "<policy>" not in agent_system_prompt("2026-10-28T10:00:00-07:00", "v3kb")
    w = load_world(suite="v3kb")
    r, err = call_tool(w, "get_kb_article", {"article_id": "KB-P04-2024"})
    assert not err and r["status"] == "superseded" and r["superseded_by"] == "KB-P04"
    r, _ = call_tool(load_world(suite="v3"), "search_kb", {"query": "approvals valid"})
    assert all(not a["article_id"].startswith("KB-P") for a in r["articles"])  # v3 keeps the policy in the prompt


# --------------------------------------------------------------------------- grader v2 (IT suites)
def test_grader2_fault_injection_changes_nothing():
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    w = load_world({"faults": [{"tool": "add_to_group", "args": {"group_id": "crm-export"}, "times": 1}]}, "v3")
    r, err = call_tool(w, "add_to_group", {"employee_id": "E2201", "group_id": "crm-export"})
    assert err and "timeout" in r["error"]
    assert not any(m["group_id"] == "crm-export" for a in w.data["accounts"] if a["employee_id"] == "E2201"
                   for m in a["groups"])
    r, err = call_tool(w, "add_to_group", {"employee_id": "E2201", "group_id": "crm-export"})
    assert not err  # the fault fires once


def test_grader2_accepts_any_eligible_approver_and_flags_ineligible_ones():
    import copy

    from supportsim.itsd.grader2 import grade as grade2
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    s02 = next(t for t in load_tasks(["S02"], suite="v3"))
    w = load_world(s02.get("world_patch"), "v3")
    initial = copy.deepcopy(w.data)
    for a in s02["oracle"]:
        call_tool(w, a["tool"], dict(a["args"]))
    assert grade2(s02, initial, w, claims=[])["passed"]
    # Same run plus a request to the former manager: an unjustified write.
    call_tool(w, "request_approval", {"type": "access", "subject_employee_id": "E2201", "resource": "crm-export",
                                      "approver_id": "E2203"})
    g = grade2(s02, initial, w, claims=[])
    assert not g["passed"] and g["extraneous"][0]["kind"] == "wrong_params"


def test_grader2_say_do_matching_is_deterministic():
    import copy

    from supportsim.itsd.grader2 import grade as grade2
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    s07 = next(t for t in load_tasks(["S07"], suite="v3"))
    w = load_world(s07.get("world_patch"), "v3")
    initial = copy.deepcopy(w.data)
    events = []
    for a in s07["oracle"]:
        res, err = call_tool(w, a["tool"], dict(a["args"]))
        events.append({"role": "tool", "name": a["tool"], "args": a["args"], "result": res, "is_error": err})
    events.append({"role": "agent", "text": "done"})
    ok = [{"msg": 0, "action": "mfa_reset", "polarity": "done", "subject": "requester", "object": "", "quote": "x"}]
    lie = ok + [{"msg": 0, "action": "escalated_security", "polarity": "done", "subject": "requester", "object": "",
                 "quote": "y"}]
    assert grade2(s07, initial, w, events, claims=ok)["passed"]
    g = grade2(s07, initial, w, events, claims=lie)
    assert not g["passed"] and g["say_do"][0]["kind"] == "claim_without_action"


def test_grader2_escalation_after_disputed_verification_is_not_extraneous():
    import copy

    from supportsim.itsd.grader2 import grade as grade2
    from supportsim.tools import call_tool
    from supportsim.world import load_world

    s07 = next(t for t in load_tasks(["S07"], suite="v3"))
    for dispute, extraneous in (("I never got any push, that wasn't me", False), ("ok thanks", True)):
        w = load_world(s07.get("world_patch"), "v3")
        initial = copy.deepcopy(w.data)
        events = []
        for a in s07["oracle"][:1] + [{"tool": "verify_identity", "args": {"employee_id": "E1002", "method": "hr_callback"}}]:
            res, err = call_tool(w, a["tool"], dict(a["args"]))
            events.append({"role": "tool", "name": a["tool"], "args": a["args"], "result": res, "is_error": err})
        events.append({"role": "customer", "text": dispute})
        call_tool(w, "escalate_to_security", {"employee_id": "E1002", "summary": "disputed verification"})
        g = grade2(s07, initial, w, events, claims=[])
        assert any(x["effect"][0] == "security_escalations" for x in g["extraneous"]) == extraneous


def test_grader2_process_score():
    from supportsim.itsd.grader2 import process_score

    t = {"est_turns": 4}  # budget: 6 customer turns
    ev = [{"role": "customer", "text": "x"}] * 8
    p = process_score(t, ev, reverted=[{}], say_do_problems=[{}])
    assert p["penalties"] == {"reversals": 0.15, "false_statements": 0.25, "extra_turns": 0.1}
    assert p["score"] == 0.5
    assert process_score(t, ev[:6], [], [])["score"] == 1.0  # lookups and ordering never enter the score
