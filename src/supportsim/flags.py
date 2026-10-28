"""Flag runs where the simulated customer leaked the answer or broke character.

Flags don't change pass/fail. They mark runs whose result can't be trusted,
so they can be read and excluded. Two layers:
  rules   always on: character-break phrases, tool or policy vocabulary, and
          expected amounts the customer said before the agent did
  judge   optional (--judge-model): a cheap model reads the scenario and the
          customer's messages and answers three yes/no questions
"""
from __future__ import annotations

import json
import re

from .providers import Provider
from .itsd.tools import TOOL_SPECS as ITSD_TOOLS
from .tools import TOOLS, V2_TOOLS

BREAK = re.compile(r"\b(as an ai|language model|simulat\w*|role-?play\w*|my instructions|the scenario|"
                   r"i am an assistant|i'm an assistant|test case|system prompt)\b", re.I)
TOOL_WORDS = re.compile(r"\b(" + "|".join(t["name"] for t in TOOLS + V2_TOOLS + ITSD_TOOLS) + r"|effective sensitivity|sod_exception|hr_unlock|refund_over_limit|fraud_review|delivery_dispute|"
                        r"unrecognized_charge|food_safety|policy section|section \d)\b", re.I)


def _amount_mentioned(amount: str, text: str) -> bool:
    return re.search(r"(?<![\d.])\$?" + re.escape(amount) + r"(?![\d])", text) is not None


# The customer echoing its own instructions ("I don't know the late-delivery policy").
ECHO = re.compile(r"\bi (don'?t|do not) know (the|your|what the|any) [\w\s-]{0,30}(polic|rules)", re.I)


def rule_flags(task: dict, events: list[dict]) -> list[dict]:
    flags = []
    first = task["user"]["persona"].split()[0].strip(",")
    # Addressing itself by its own name ("Thanks, Priya") means it has confused the roles.
    self_name = re.compile(rf"\b(thanks|thank you|hi|hello|hey|ok|okay|great),? {re.escape(first)}\b", re.I)
    leak = task.get("leak_check", {})
    said_by_agent: set[str] = set()  # amounts and phrases the agent has already said
    for i, ev in enumerate(events):
        if ev["role"] == "agent":
            for a in leak.get("amounts", []):
                if _amount_mentioned(a, ev["text"]):
                    said_by_agent.add(a)
            for p in leak.get("phrases", []):
                if re.search(p, ev["text"], re.I):
                    said_by_agent.add(p)
        if ev["role"] != "customer":
            continue
        t = ev["text"]
        if m := BREAK.search(t):
            flags.append({"type": "broke_character", "event": i, "match": m.group(0)})
        if m := self_name.search(t):
            flags.append({"type": "broke_character", "event": i, "match": m.group(0)})
        if m := ECHO.search(t):
            flags.append({"type": "echoed_instructions", "event": i, "match": m.group(0)})
        if m := TOOL_WORDS.search(t):
            flags.append({"type": "leaked_internal_vocabulary", "event": i, "match": m.group(0)})
        for a in leak.get("amounts", []):
            if a not in said_by_agent and _amount_mentioned(a, t):
                flags.append({"type": "leaked_expected_amount", "event": i, "match": a})
        for p in leak.get("phrases", []):
            if p not in said_by_agent and re.search(p, t, re.I):
                flags.append({"type": "leaked_solution_phrase", "event": i, "match": p})
    return flags


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "leaked_solution": {"type": "boolean"},
        "broke_character": {"type": "boolean"},
        "revealed_hidden_info_unprompted": {"type": "boolean"},
        "explanation": {"type": "string"},
    },
    "required": ["leaked_solution", "broke_character", "revealed_hidden_info_unprompted", "explanation"],
    "additionalProperties": False,
}


def judge_flags(judge: Provider, task: dict, events: list[dict]) -> list[dict]:
    """Ask a model whether the simulated customer behaved. Uses structured output when the provider supports it."""
    convo = "\n".join(f"{e['role'].upper()}: {e['text']}" for e in events if e["role"] in ("customer", "agent"))
    prompt = f"""You are auditing a simulated customer in a support-agent benchmark. The customer was given a hidden
scenario and must (a) never tell the agent the correct resolution or policy, (b) stay in character as a human
customer, and (c) follow these reveal rules: {json.dumps(task['user'].get('reveal_rules', []))}.

The correct resolution, which the customer must NOT have suggested: {task.get('resolution_summary', '')}

Conversation:
{convo}

Answer about the CUSTOMER's messages only. leaked_solution: did the customer state or strongly hint the correct
resolution, amount or policy before the agent did? broke_character: did the customer talk like an AI, mention a
simulation, or act like an assistant? revealed_hidden_info_unprompted: did the customer volunteer a detail the
reveal rules said to hold back? A detail is NOT unprompted if the agent asked for it, mentioned it first, or asked the
customer to confirm it. Only flag clear cases. Give a one-sentence explanation."""
    conv = judge.start("You check transcripts carefully and answer in JSON.")
    if hasattr(conv, "send_user_json"):
        data = conv.send_user_json(prompt, JUDGE_SCHEMA)
    else:
        text = conv.send_user(prompt + "\nReply with only a JSON object with keys: "
                              + ", ".join(JUDGE_SCHEMA["required"])).text
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    flags = []
    for k in ("leaked_solution", "broke_character", "revealed_hidden_info_unprompted"):
        if data.get(k):
            flags.append({"type": f"judge:{k}", "explanation": data.get("explanation", "")})
    return flags
