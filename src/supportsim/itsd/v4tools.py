"""v4real tools: the v3 IT tools plus a policy wiki, a lagging directory replica, devices and sessions, travel,
MFA exceptions, ownership hand-off and removable media.

As everywhere in this benchmark, tools enforce data integrity only, never policy. Two behaviours copy real systems:
- `get_account` and `list_group_members` read a directory replica that can lag the HR record (`as_of`); pass
  live=true to `get_account` for the current directory record.
- `unlock_account` succeeds, but if a device is still retrying an old password the account locks again within
  minutes (the next read shows it locked). This is what the source threads describe.
"""
from __future__ import annotations

import copy
import re

from ..world import World
from . import tools as v3
from .tools import ToolError, _acct, _asset, _emp, _group, _new_approval, _obj, _s, EMP, S

APPROVAL_TYPES_V4 = ["access", "license", "sod_exception", "hr_unlock", "reenable", "retained_access",
                     "travel_confirmation", "removable_media", "external_share"]


def _until(s, field: str):
    """A date or a date-time. A plain date (2026-11-11) means the end of that day, local time."""
    v = _s(s).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        v = f"{v}T23:59:00-07:00"
    return v3._when(v, field)


# --------------------------------------------------------------------------- wiki
def _pages(w: World) -> list[dict]:
    return w.data["wiki"] + w.data["kb"]


def search_wiki(w: World, query) -> dict:
    words = set(re.findall(r"[a-z0-9]+", _s(query).lower())) - {"a", "the", "to", "my", "how", "i", "of", "and",
                                                                  "for", "in", "on", "is", "what"}
    scored = []
    for p in _pages(w):
        text = (p.get("title", "") + " " + p.get("body", "")).lower()
        toks = set(re.findall(r"[a-z0-9]+", text))
        s = len(words & toks)
        if s:
            scored.append((s, p))
    scored.sort(key=lambda x: -x[0])
    return {"results": [{"page_id": p.get("page_id") or p.get("article_id"), "title": p["title"],
                         "type": p.get("type", "kb"), "revision": p.get("revision"),
                         "snippet": re.sub(r"\s+", " ", p["body"])[:200]} for _, p in scored[:8]],
            "hint": "Open a page with get_wiki_page. The policy index is page INDEX."}


def get_wiki_page(w: World, page_id, section=None) -> dict:
    pid = _s(page_id).strip().upper()
    p = next((x for x in _pages(w) if (x.get("page_id") or x.get("article_id", "")).upper() == pid), None)
    if not p:
        raise ToolError(f"No page {page_id}. See page INDEX for the list.")
    body = p["body"]
    if section:
        # Return the part of the page from the first heading or line that mentions the section.
        lines = body.splitlines()
        idx = next((i for i, l in enumerate(lines) if _s(section).lower() in l.lower()), None)
        if idx is not None:
            body = "\n".join(lines[idx: idx + 80])
    meta = {k: v for k, v in p.items() if k not in ("body",)}
    return {**meta, "body": body}


# --------------------------------------------------------------------------- directory (replica vs live)
def _replica(w: World, eid: str) -> dict:
    return w.data.get("replica", {}).get(eid, {})


def get_account(w: World, employee_id, live=False) -> dict:
    a = copy.deepcopy(_acct(w, employee_id))
    e = _emp(w, employee_id)
    profile = {"department": e["department"], "manager_id": e["manager_id"], "employment_status": e["status"]}
    if str(live).lower() in ("true", "1", "yes"):
        return {**a, "directory_profile": profile, "source": "live", "as_of": w.data["now"]}
    rep = _replica(w, a["employee_id"])
    a.update(rep.get("account", {}))
    profile.update(rep.get("profile", {}))
    return {**a, "directory_profile": profile, "source": "replica",
            "as_of": rep.get("as_of", w.data["replica_default_as_of"])}


def list_group_members(w: World, group_id, page=1) -> dict:
    out = v3.list_group_members(w, group_id, page)
    for m in out["members"]:
        rep = _replica(w, m["employee_id"])
        acct = _acct(w, m["employee_id"])
        m["account_status"] = rep.get("account", {}).get("status", acct["status"])
    out["source"] = "replica"
    out["as_of"] = w.data["replica_default_as_of"]
    return out


# --------------------------------------------------------------------------- credentials
def verify_identity(w: World, employee_id, method, approver_id=None) -> dict:
    e = _emp(w, employee_id)
    if method == "knowledge_questions":
        script = w.data["verification_script"].get(e["employee_id"], {})
        return {"employee_id": e["employee_id"], "method": method,
                "result": script.get("knowledge_questions", "passed"),
                "detail": "The person answered the registered security questions."}
    if method == "mfa_push" and _acct(w, e["employee_id"])["status"] == "disabled":
        raise ToolError("Push not available: the account is disabled.")
    try:
        return v3.verify_identity(w, employee_id, method, approver_id)
    except ToolError as err:
        if "method must be" in str(err):
            raise ToolError("method must be mfa_push, hr_callback, manager_attestation or knowledge_questions.") from None
        raise


def unlock_account(w: World, employee_id) -> dict:
    out = v3.unlock_account(w, employee_id)
    a = _acct(w, employee_id)
    stale = [d for d in a.get("devices", []) if d.get("session") == "active" and d.get("auth") == "failing_old_password"]
    if stale:  # the stale client retries within minutes and locks the account again
        a["status"] = "locked"
        a["lock_count_today"] = a.get("lock_count_today", 0) + 1
        a["lock_reason"] = (f"Too many failed sign-ins (5) from device {stale[0]['device_id']} "
                            f"({stale[0]['label']}) shortly after the last unlock.")
    return out


def reenable_account(w: World, employee_id) -> dict:
    a = _acct(w, employee_id)
    if a["status"] != "disabled":
        raise ToolError(f"The account is not disabled (status: {a['status']}).")
    a["status"], a["lock_reason"] = "active", None
    a.setdefault("history", []).append({"event": "re-enabled", "at": w.data["now"]})
    return {"employee_id": a["employee_id"], "status": "active"}


def list_devices(w: World, employee_id) -> dict:
    a = _acct(w, employee_id)
    return {"employee_id": a["employee_id"], "devices": copy.deepcopy(a.get("devices", [])),
            "authenticators": copy.deepcopy(a.get("authenticators", []))}


def revoke_device_session(w: World, employee_id, device_id) -> dict:
    a = _acct(w, employee_id)
    d = next((d for d in a.get("devices", []) if d["device_id"].lower() == _s(device_id).lower()), None)
    if not d:
        raise ToolError(f"No device {device_id} on {a['employee_id']}'s account.")
    if d.get("session") == "revoked":
        raise ToolError(f"{d['device_id']} has no active session.")
    d["session"], d["auth"] = "revoked", None
    return {"employee_id": a["employee_id"], "device_id": d["device_id"], "session": "revoked"}


def revoke_authenticator(w: World, employee_id, authenticator_id) -> dict:
    a = _acct(w, employee_id)
    k = next((k for k in a.get("authenticators", []) if k["authenticator_id"].lower() == _s(authenticator_id).lower()), None)
    if not k:
        raise ToolError(f"No authenticator {authenticator_id} on {a['employee_id']}'s account.")
    if k["status"] == "revoked":
        raise ToolError(f"{k['authenticator_id']} is already revoked.")
    k["status"] = "revoked"
    return {"employee_id": a["employee_id"], "authenticator_id": k["authenticator_id"], "status": "revoked"}


def grant_mfa_exception(w: World, employee_id, account, expires_at) -> dict:
    a = _acct(w, employee_id)
    if account not in ("standard", "admin"):
        raise ToolError("account must be standard or admin.")
    if account == "admin" and not a.get("admin_account"):
        raise ToolError(f"{a['employee_id']} has no admin account.")
    exp = _until(expires_at, "expires_at")
    x = {"employee_id": a["employee_id"], "account": account, "expires_at": exp.isoformat(), "granted_at": w.data["now"]}
    w.data["mfa_exceptions"].append(x)
    return {**x, "note": "One-time sign-in codes will be sent to the HR-record mobile until the exception expires."}


def report_security_incident(w: World, employee_id, kind, summary) -> dict:
    e = _emp(w, employee_id)
    n = len(w.data["security_incidents"])
    x = {"incident_id": f"SEC-{9001 + n}", "employee_id": e["employee_id"], "kind": _s(kind), "summary": _s(summary),
         "at": w.data["now"]}
    w.data["security_incidents"].append(x)
    return x


def release_device_quarantine(w: World, asset_id) -> dict:
    a = _asset(w, asset_id)
    if not a.get("quarantined"):
        raise ToolError(f"{a['asset_id']} is not quarantined.")
    a["quarantined"] = False  # graded as its own effect (quarantine_released), so not added to the asset history
    return {"asset_id": a["asset_id"], "quarantined": False}


# --------------------------------------------------------------------------- access lifecycle
def set_membership_expiry(w: World, employee_id, group_id, expires_at) -> dict:
    a = _acct(w, employee_id)
    g = _group(w, group_id)
    m = next((m for m in a["groups"] if m["group_id"] == g["group_id"]), None)
    if not m:
        raise ToolError(f"{a['employee_id']} is not in {g['group_id']}.")
    m["expires_at"] = _until(expires_at, "expires_at").date().isoformat()
    return {"employee_id": a["employee_id"], "group_id": g["group_id"], "expires_at": m["expires_at"]}


def schedule_account_disable(w: World, employee_id, at) -> dict:
    a = _acct(w, employee_id)
    when = v3._when(at, "at").isoformat()
    w.data["scheduled_disables"].append({"employee_id": a["employee_id"], "at": when})
    return {"employee_id": a["employee_id"], "disable_at": when}


def _resource(w: World, rid):
    g = v3.Org(w.data).group(rid)
    if g:
        return "group", g
    s = next((s for s in w.data["service_accounts"] if s["account_id"].lower() == _s(rid).lower()), None)
    if s:
        return "service_account", s
    raise ToolError(f"No group or service account {rid}.")


def transfer_ownership(w: World, resource_id, new_owner) -> dict:
    kind, r = _resource(w, resource_id)
    emp = v3.Org(w.data).emp(new_owner)
    if emp:
        owner = emp["employee_id"]
    elif "@" in _s(new_owner):  # the system accepts external guest owners; policy decides whether that's allowed
        owner = _s(new_owner).strip().lower()
    else:
        raise ToolError("new_owner must be an employee ID or an email address.")
    r["owner_id"] = owner
    return {"resource_id": r.get("group_id") or r["account_id"], "kind": kind, "owner": owner}


def get_service_account(w: World, account_id=None, owner_id=None) -> dict:
    if account_id:
        _, s = _resource(w, account_id)
        return copy.deepcopy(s)
    oid = _s(owner_id).upper()
    return {"service_accounts": [copy.deepcopy(s) for s in w.data["service_accounts"] if s["owner_id"] == oid]}


# --------------------------------------------------------------------------- travel, devices, data
def enable_roaming(w: World, asset_id, until) -> dict:
    a = _asset(w, asset_id)
    if a["type"] != "phone":
        raise ToolError("Roaming applies to phones only.")
    a["roaming"] = {"enabled": True, "until": _until(until, "until").date().isoformat()}
    return {"asset_id": a["asset_id"], "roaming": a["roaming"]}


def disable_roaming(w: World, asset_id) -> dict:
    a = _asset(w, asset_id)
    if not (a.get("roaming") or {}).get("enabled"):
        raise ToolError(f"Roaming is not enabled on {a['asset_id']}.")
    a["roaming"] = {"enabled": False, "until": None}
    return {"asset_id": a["asset_id"], "roaming": a["roaming"]}


def submit_travel_request(w: World, employee_id, countries, depart, return_date, devices=None, reason=None) -> dict:
    e = _emp(w, employee_id)
    cs = countries if isinstance(countries, list) else [c.strip() for c in _s(countries).split(",") if c.strip()]
    sec = sorted(v3.Org(w.data).members("security-approvers"))[0]
    appr = _new_approval(w, "travel", e["employee_id"], "overseas_travel", sec)
    x = {"request_id": f"TRV-{7301 + len(w.data['travel_requests'])}", "employee_id": e["employee_id"],
         "countries": cs, "depart": _s(depart), "return": _s(return_date), "devices": devices or [],
         "reason": _s(reason), "approval_id": appr["approval_id"], "status": appr["status"]}
    w.data["travel_requests"].append(x)
    return x


def get_device_policy(w: World, employee_id, live=False) -> dict:
    e = _emp(w, employee_id)
    pol = w.data["device_policy"].get(e["employee_id"], {})
    if str(live).lower() in ("true", "1", "yes"):
        return {"employee_id": e["employee_id"], **pol.get("live", {}), "source": "live", "as_of": w.data["now"]}
    return {"employee_id": e["employee_id"], **pol.get("cached", pol.get("live", {})), "source": "cache"}


def enable_usb_write(w: World, asset_id, until) -> dict:
    a = _asset(w, asset_id)
    if a["type"] != "laptop":
        raise ToolError("USB write applies to laptops only.")
    a["usb_write"] = {"enabled": True, "until": _until(until, "until").date().isoformat()}
    return {"asset_id": a["asset_id"], "usb_write": a["usb_write"]}


def request_approval(w: World, type, subject_employee_id, resource, approver_id) -> dict:  # noqa: A002
    if type not in APPROVAL_TYPES_V4:
        raise ToolError(f"type must be one of {', '.join(APPROVAL_TYPES_V4)}.")
    return _new_approval(w, type, subject_employee_id, resource, approver_id)


V4_IMPL = {f.__name__: f for f in (
    search_wiki, get_wiki_page, get_account, list_group_members, verify_identity, unlock_account, reenable_account,
    list_devices, revoke_device_session, revoke_authenticator, grant_mfa_exception, report_security_incident,
    release_device_quarantine, set_membership_expiry, schedule_account_disable, transfer_ownership,
    get_service_account, enable_roaming, disable_roaming, submit_travel_request, get_device_policy, enable_usb_write,
    request_approval)}
V4_WRITE_TOOLS = {"reenable_account", "revoke_device_session", "revoke_authenticator", "grant_mfa_exception",
                  "report_security_incident", "release_device_quarantine", "set_membership_expiry",
                  "schedule_account_disable", "transfer_ownership", "enable_roaming", "disable_roaming",
                  "submit_travel_request", "enable_usb_write"}
HIDDEN_IN_V4 = {"search_kb", "get_kb_article"}  # the wiki tools replace them

D = {"type": "string"}
V4_SPECS = [
    {"name": "search_wiki",
     "description": "Search the policy wiki (POL-100, procedural guides PG-*, standards STD-*, guidance GUI-*, reference "
                    "REF-*) and KB how-to articles. Returns page IDs, titles and snippets. Page INDEX lists the "
                    "policy pages.",
     "input_schema": _obj({"query": S}, ["query"])},
    {"name": "get_wiki_page",
     "description": "Read a wiki page or KB article by page_id (e.g. POL-100, PG-01-07, KB-1204). Optional section: "
                    "returns the part of the page starting at the first line that mentions it.",
     "input_schema": _obj({"page_id": S, "section": S}, ["page_id"])},
    {"name": "get_account",
     "description": "Directory account: status (active, locked, disabled), lock_reason, lock_count_today, MFA devices, "
                    "recent sign-ins, group memberships with expiry, admin_account (if any), and directory_profile "
                    "(department, manager_id, employment_status as the directory has them). Reads the directory "
                    "replica by default; the result's `source` and `as_of` say which copy and how fresh. live=true "
                    "reads the live directory.",
     "input_schema": _obj({"employee_id": EMP, "live": {"type": "boolean"}}, ["employee_id"])},
    {"name": "list_group_members",
     "description": "Direct members of a group, 10 per page (page 1, 2, ...), with added_at, expires_at and "
                    "account_status from the directory replica. has_more says whether there are more pages.",
     "input_schema": _obj({"group_id": S, "page": {"type": "integer"}}, ["group_id"])},
    {"name": "verify_identity",
     "description": "Run an identity check on an employee. method: mfa_push (push to their registered MFA devices), "
                    "hr_callback (call the mobile on the HR record), manager_attestation (needs approver_id; creates "
                    "an identity_attestation approval), or knowledge_questions (the person answers their registered "
                    "security questions in chat). Returns the result.",
     "input_schema": _obj({"employee_id": EMP, "method": {"type": "string", "enum": [
         "mfa_push", "hr_callback", "manager_attestation", "knowledge_questions"]}, "approver_id": EMP},
         ["employee_id", "method"])},
    {"name": "reenable_account", "description": "Re-enable a disabled directory account.",
     "input_schema": _obj({"employee_id": EMP}, ["employee_id"])},
    {"name": "list_devices",
     "description": "Devices and sessions signed in to an employee's account (laptops, phones, tablets, mail apps) with "
                    "registered_at, last_seen, last_city, session (active/revoked) and auth (ok, or "
                    "failing_old_password), plus their authenticators (security keys, authenticator apps) and status.",
     "input_schema": _obj({"employee_id": EMP}, ["employee_id"])},
    {"name": "revoke_device_session", "description": "Sign a device out of an employee's account and remove its session.",
     "input_schema": _obj({"employee_id": EMP, "device_id": S}, ["employee_id", "device_id"])},
    {"name": "revoke_authenticator", "description": "Revoke an authenticator (security key or authenticator app) so it "
                                                    "can no longer be used to sign in.",
     "input_schema": _obj({"employee_id": EMP, "authenticator_id": S}, ["employee_id", "authenticator_id"])},
    {"name": "grant_mfa_exception",
     "description": "Grant a temporary MFA exception: one-time sign-in codes instead of the usual factor, on the "
                    "employee's standard or admin account, until expires_at (ISO 8601).",
     "input_schema": _obj({"employee_id": EMP, "account": {"type": "string", "enum": ["standard", "admin"]},
                           "expires_at": S}, ["employee_id", "account", "expires_at"])},
    {"name": "report_security_incident",
     "description": "Report a security incident to Security. kind: lost_device, data_incident or other.",
     "input_schema": _obj({"employee_id": EMP, "kind": {"type": "string", "enum": ["lost_device", "data_incident", "other"]},
                           "summary": S}, ["employee_id", "kind", "summary"])},
    {"name": "release_device_quarantine", "description": "Release a device from inactivity quarantine.",
     "input_schema": _obj({"asset_id": S}, ["asset_id"])},
    {"name": "set_membership_expiry",
     "description": "Set or change the expiry date (ISO 8601) of an existing group membership.",
     "input_schema": _obj({"employee_id": EMP, "group_id": S, "expires_at": S}, ["employee_id", "group_id", "expires_at"])},
    {"name": "schedule_account_disable", "description": "Schedule an account to be disabled at a date-time (ISO 8601).",
     "input_schema": _obj({"employee_id": EMP, "at": S}, ["employee_id", "at"])},
    {"name": "transfer_ownership",
     "description": "Transfer ownership of a group or service account to new_owner (an employee ID, or an email "
                    "address for an external/guest owner).",
     "input_schema": _obj({"resource_id": S, "new_owner": S}, ["resource_id", "new_owner"])},
    {"name": "get_service_account",
     "description": "A service account by account_id, or the service accounts owned by owner_id.",
     "input_schema": _obj({"account_id": S, "owner_id": EMP}, [])},
    {"name": "enable_roaming", "description": "Enable international roaming (and remote wipe) on a company phone until a date.",
     "input_schema": _obj({"asset_id": S, "until": S}, ["asset_id", "until"])},
    {"name": "disable_roaming", "description": "Turn international roaming off on a company phone.",
     "input_schema": _obj({"asset_id": S}, ["asset_id"])},
    {"name": "submit_travel_request",
     "description": "Submit a GUI-OVS Part Two travel request to Security for an employee: countries visited or "
                    "passed through, depart and return_date (ISO dates), devices (asset IDs) and reason. Creates a "
                    "`travel` approval decided by Security; returns its status.",
     "input_schema": _obj({"employee_id": EMP, "countries": {"type": "array", "items": D}, "depart": S,
                           "return_date": S, "devices": {"type": "array", "items": D}, "reason": S},
                          ["employee_id", "countries", "depart", "return_date"])},
    {"name": "get_device_policy",
     "description": "Device settings policy for an employee's laptop (e.g. USB write). Reads the policy cache by "
                    "default (with its as_of); live=true reads the live policy service.",
     "input_schema": _obj({"employee_id": EMP, "live": {"type": "boolean"}}, ["employee_id"])},
    {"name": "enable_usb_write", "description": "Enable writing to USB storage on a laptop until a date.",
     "input_schema": _obj({"asset_id": S, "until": S}, ["asset_id", "until"])},
    {"name": "request_approval",
     "description": "Request an approval in the approval system. Types: " + ", ".join(APPROVAL_TYPES_V4) + ". resource is "
                    "the group or product (access, license, sod_exception, retained_access), 'account' (hr_unlock, "
                    "reenable), 'overseas_travel' (travel_confirmation), the asset ID (removable_media) or "
                    "'external_share'. Returns the approval and its status (approvers often answer at once).",
     "input_schema": _obj({"type": {"type": "string", "enum": APPROVAL_TYPES_V4}, "subject_employee_id": EMP,
                           "resource": S, "approver_id": EMP}, ["type", "subject_employee_id", "resource", "approver_id"])},
]


def tool_specs() -> list[dict]:
    names = {t["name"] for t in V4_SPECS}
    return [t for t in v3.TOOL_SPECS if t["name"] not in names and t["name"] not in HIDDEN_IN_V4] + V4_SPECS
