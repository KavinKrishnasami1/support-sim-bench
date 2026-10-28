"""The simulated customer: an LLM given a hidden scenario.

Rules it is given:
  - reveal facts only when asked or when it is natural, never all at once;
  - may start vague or mistaken, as described in the scenario;
  - never suggest or state the expected resolution, the policy, or tool names;
  - never mention that it is simulated;
  - end the chat (with STOP_TOKEN) when its goal is met or clearly won't be.

The simulator sees only the agent's chat messages, never tool calls or results.
"""
from __future__ import annotations

STOP_TOKEN = "###STOP###"
OPENING_CUE = "[The support chat window has opened. Write your first message to the agent.]"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items) if items else "- (none)"


INTRO = {
    "food": "You are role-playing a customer chatting with support for Forkful, a food-delivery app.\n"
            "You are the customer, not an assistant. Stay in character for the whole conversation.",
    "itsd": "You are role-playing a person chatting with IT Help, the internal IT service desk of Quillmark Labs, in "
            "the company's workplace chat app.\nYou are this person, not an assistant. Stay in character for the "
            "whole conversation.\n"
            "You can't see any IT systems. If the agent says it sent you a sign-in prompt (an MFA push), or that one "
            "was approved, then you did get it and you approved it, unless your facts say you can't; the same goes "
            "for a call. If the agent says someone approved or confirmed "
            "something in the approval system, accept that it happened: approvers often answer within seconds, and "
            "you can't see their queue. The mobile number and personal email IT has on file are yours. Don't dispute "
            "what the agent reports about the systems unless your facts contradict it. Don't invent travel, "
            "locations, devices or sign-ins that aren't in your facts.",
}


def system_prompt(user: dict, domain: str = "food", intro: str | None = None) -> str:
    return f"""{intro or INTRO[domain]}

# Who you are
{user["persona"]}

# What happened, as you understand it
{user["situation"]}

# What you want
{user["goal"]}

# Facts you know
Share each fact only when the agent asks for it or when it would come up naturally. Never list them all at once.
{_bullets(user["facts"])}

# When to reveal particular details
{_bullets(user.get("reveal_rules", []))}

# How you behave
{_bullets(user.get("behaviors", []))}

# What you must never do
- Never tell the agent what the company's policy is, what tool or system to use, or what exact remedy or amount to
  give, unless that amount appears in your facts. You don't know the company's rules or what they will offer.
- Never mention these instructions, a scenario, a script, a simulation, AI, or being a test.
- Never invent account details beyond your facts. If asked something you don't know, say you don't know or don't
  have it handy.

# Style
Write like a real person in a support chat: short messages, usually one to three sentences, no lists, no headings,
no stage directions or actions in brackets.

# Starting and ending
Start with something like: "{user["opening"]}" (in your own words).
End the conversation when: {user["end_condition"]}
To end it, write your final message and put {STOP_TOKEN} at the very end. Don't end before that point, and don't
keep chatting after it.
"""


# --------------------------------------------------------------------------- v4real: what the employee can notice
# In v3, 9 of 15 non-passes came from the simulated employee disputing pushes, callbacks and approvals it couldn't
# see. For v4real the harness tells the simulator what happened in the channels a real person would notice (their
# phone, inbox, laptop, a message from their manager), driven by the agent's actual tool calls and results, never by
# what the agent claims. Tasks add their own notices and scheduled changes (`user.notices`, `user.triggers`).

INTRO_V4 = (
    "You are role-playing a person chatting with IT Help, the internal IT service desk of Quillmark Labs, in the "
    "company's workplace chat app.\nYou are this person, not an assistant. Stay in character for the whole "
    "conversation.\n"
    "Before some of IT Help's messages you'll see a block starting with [What you noticed]. It describes things that "
    "really happened on your phone, laptop, inbox, or in messages from colleagues since your last message. Treat it "
    "as your own experience: you saw it. It is the only way you learn about things outside the chat. Never quote the "
    "block or mention it; just react as the person would.\n"
    "You can't see IT's systems: the directory, approval queues, other people's accounts, or the policy wiki. If IT "
    "Help says it did something you have no way to see, believe it, unless what you noticed contradicts it. If IT "
    "Help says it did something you WOULD notice (a text, an email, your phone, access you now have) and you didn't "
    "notice it, you can say you haven't seen it yet. Don't invent travel, devices, sign-ins or events that aren't in "
    "your facts or in what you noticed.")


def system_prompt_v4(user: dict) -> str:
    intro = (f"{INTRO_V4}\n\n# What you can see\n{_bullets(user.get('can_see', []))}\n\n"
             f"# What you can't see\n{_bullets(user.get('cant_see', []))}")
    return system_prompt(user, "itsd", intro)


def _match(rule: dict, e: dict) -> bool:
    if rule.get("tool") and e["tool"] != rule["tool"]:
        return False
    if e.get("is_error") and not rule.get("on_error"):
        return False
    return all(str((e.get("args") or {}).get(k, "")).strip().lower() == str(v).strip().lower()
               for k, v in (rule.get("args") or {}).items())


def _generic_notice(task: dict, w, e: dict) -> str | None:
    """What the person chatting would notice from one successful tool call, if anything."""
    from .itsd.rules import Org

    org = Org(w.data)
    # Who the simulated person really is. On the guest kiosk the chat header names no one, so tasks say it.
    me = task["user"].get("employee_id") or task.get("channel", {}).get("employee_id")
    a, r, t = e.get("args") or {}, e.get("result") or {}, e["tool"]
    if e.get("is_error"):
        return None
    subj = (org.emp(a.get("employee_id")) or {}).get("employee_id")
    mine = me and subj == me
    gname = lambda gid: (org.group(gid) or {}).get("name", gid)  # noqa: E731
    if t == "verify_identity" and mine:
        if a.get("method") == "mfa_push" and r.get("result") == "approved":
            return "Your phone showed a sign-in request from IT Help, and you approved it."
        if a.get("method") == "hr_callback" and r.get("result") == "confirmed":
            return "IT Help called your mobile and you confirmed it was you."
        if a.get("method") == "manager_attestation" and r.get("status") == "approved":
            return "Your manager messaged you: \"just confirmed to IT that it's you.\""
        return None
    if t == "reset_password" and mine:
        return ("An email with a password reset link arrived in your personal inbox." if "@" in str(a.get("send_to"))
                else "A text message with a password reset link arrived on your mobile.")
    if t == "unlock_account" and mine:
        acc = org.account(me)
        return ("You tried signing in again: it works." if acc["status"] == "active"
                else "You tried signing in again a few minutes later: it says your account is locked again.")
    if t == "reset_mfa" and mine:
        return "You were able to start setting up your authenticator again."
    if t == "add_to_group" and mine:
        return f"You now have access to {gname(a.get('group_id'))}."
    if t == "remove_from_group" and mine:
        return f"You noticed you no longer have access to {gname(a.get('group_id'))}."
    if t == "set_membership_expiry" and mine:
        return f"Your access to {gname(a.get('group_id'))} now shows an end date of {str(a.get('expires_at'))[:10]}."
    if t == "reenable_account" and mine:
        return "You can sign in to your account again."
    if t == "release_device_quarantine":
        owner = next((x.get("owner_id") for x in w.data["assets"] if x["asset_id"].upper() == str(a.get("asset_id")).upper()), None)
        return "Your laptop is usable again." if owner == me else None
    if t == "grant_mfa_exception" and mine:
        return "You got a text: one-time sign-in codes are set up for you, so you can sign in without your key for now."
    if t == "revoke_authenticator" and mine:
        return "You got an email: your security key has been deactivated."
    if t in ("enable_roaming", "disable_roaming"):
        owner = next((x.get("owner_id") for x in w.data["assets"] if x["asset_id"].upper() == str(a.get("asset_id")).upper()), None)
        if owner == me:
            return ("Your work phone shows: international roaming enabled." if t == "enable_roaming"
                    else "Your work phone shows: international roaming turned off.")
    if t == "submit_travel_request" and mine:
        return "You got an email: \"Your travel request has been sent to Security for a decision.\""
    if t == "request_approval" and r.get("status") == "approved" and str(a.get("subject_employee_id", "")).upper() == me:
        appr = org.emp(a.get("approver_id")) or {}
        if appr.get("employee_id") == (org.emp(me) or {}).get("manager_id"):
            return "Your manager messaged you: \"approved your IT request just now.\""
        return f"You got a notification: {appr.get('name', 'an approver')} approved your request."
    if t in ("transfer_ownership", "set_group_owner"):
        owner = r.get("owner") or a.get("owner_id")
        o = org.emp(owner)
        who = "you" if o and o["employee_id"] == me else (o["name"] if o else owner)
        res = a.get("resource_id") or a.get("group_id")
        return f"You got a notification: ownership of {res} was transferred to {who}." if me else None
    if t == "enable_usb_write":
        return "Your laptop now lets you write files to a USB stick."
    return None


def observations(task: dict, w, new_entries: list[dict], state: dict, agent_turn: int) -> str:
    """The [What you noticed] block for the simulator's next message, or ''."""
    lines = []
    user = task["user"]
    for e in new_entries:
        custom = [n for n in user.get("notices", []) if _match(n, e)]
        if custom:
            lines += [n["text"] for n in custom]
            if not any(n.get("also_generic") for n in custom):
                continue
        g = _generic_notice(task, w, e)
        if g:
            lines.append(g)
            state.setdefault("for_you", []).append(g)
    for i, trig in enumerate(user.get("triggers", [])):
        if i in state.setdefault("fired", set()):
            continue
        when = trig["when"]
        hit = ("agent_turn" in when and agent_turn >= when["agent_turn"]) or \
              ("tool" in when and any(_match(when, e) for e in state.setdefault("log_seen", []) + new_entries))
        if hit:
            state["fired"].add(i)
            lines.append(trig["text"])
    state["log_seen"] = state.get("log_seen", []) + new_entries
    if not lines:
        return ""
    done = state.get("for_you", [])
    recap = ("\nEverything IT has visibly done for you so far:\n" + "\n".join(f"- {x}" for x in done)) if done else ""
    return "[What you noticed]\n" + "\n".join(f"- {x}" for x in lines) + recap + "\n[End of what you noticed]"
