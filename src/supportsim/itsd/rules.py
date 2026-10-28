"""Policy facts the grader needs: who must approve, effective sensitivity, what counts as an approval.

These implement world/v3/policy.md sections 4-8 as functions of the world data, so the grader can judge any run,
not only the action sequences a task anticipated. Tools never call these: tools don't enforce policy.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

LEVEL = {"standard": 0, "sensitive": 1, "privileged": 2}
ROLES = {"standard": ["manager"], "sensitive": ["manager", "owner"], "privileged": ["manager", "security"]}
APPROVAL_DAYS = 14
CONTRACTOR_MAX_DAYS = 90


def dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def day(s: str) -> date:
    return date.fromisoformat(s[:10])


class Org:
    def __init__(self, data: dict):
        self.d = data
        self.now = dt(data["now"])
        self.today = self.now.date()
        self._emp = {e["employee_id"]: e for e in data["employees"]}
        self._grp = {g["group_id"]: g for g in data["groups"]}

    def emp(self, eid) -> dict | None:
        return self._emp.get(str(eid or "").strip().upper())

    def group(self, gid) -> dict | None:
        return self._grp.get(str(gid or "").strip().lower())

    def account(self, eid) -> dict | None:
        eid = str(eid or "").strip().upper()
        return next((a for a in self.d["accounts"] if a["employee_id"] == eid), None)

    def members(self, gid) -> list[str]:
        return [a["employee_id"] for a in self.d["accounts"] if any(m["group_id"] == gid for m in a["groups"])]

    # -- section 5: who approves in a person's place
    def stands_in(self, person_id, _seen=None) -> str | None:
        _seen = _seen or set()
        p = self.emp(person_id)
        if not p or p["employee_id"] in _seen:
            return None
        _seen.add(p["employee_id"])
        if p["status"] == "active":
            return p["employee_id"]
        if p["status"] == "on_leave":
            dlg = p.get("delegate")
            if dlg and day(dlg["valid_from"]) <= self.today <= day(dlg["valid_to"]):
                d = self.emp(dlg["employee_id"])
                if d and d["status"] == "active":
                    return d["employee_id"]
            return self.stands_in(p.get("manager_id"), _seen)
        return None  # terminated people can't approve

    def manager_approver(self, subject) -> str | None:
        s = self.emp(subject)
        return self.stands_in(s.get("manager_id")) if s else None

    def owner_approver(self, subject, gid) -> str | None:
        g = self.group(gid)
        if not g:
            return None
        if g["owner_id"] == subject:  # no one approves their own access: the owner's manager stands in
            return self.manager_approver(subject)
        return self.stands_in(g["owner_id"])

    def in_group_now(self, eid, gid) -> bool:
        return eid in self.members(gid)

    # -- section 4: nesting
    def ancestors(self, gid) -> list[str]:
        out, todo = [], list((self.group(gid) or {}).get("nested_in", []))
        while todo:
            x = todo.pop()
            if x not in out:
                out.append(x)
                todo += (self.group(x) or {}).get("nested_in", [])
        return out

    def effective_sensitivity(self, gid) -> str:
        levels = [self.group(x)["sensitivity"] for x in [gid, *self.ancestors(gid)] if self.group(x)]
        return max(levels, key=LEVEL.__getitem__) if levels else "standard"

    # -- section 4: does one approval satisfy one role
    def approval_counts(self, a: dict, role: str, subject: str, resource: str, type_: str) -> bool:
        if a.get("status") != "approved" or a.get("type") != type_:
            return False
        if a.get("subject_employee_id") != subject or str(a.get("resource", "")).lower() != resource.lower():
            return False
        if not a.get("decided_at") or self.now - dt(a["decided_at"]) > timedelta(days=APPROVAL_DAYS):
            return False
        who = a.get("approver_id")
        if who == subject:
            return False
        if role == "manager":
            return who == self.manager_approver(subject)
        if role == "owner":
            return who == self.owner_approver(subject, resource)
        if role == "security":
            return who in self.members("security-approvers") and (self.emp(who) or {}).get("status") == "active"
        if role == "people_ops":
            return who in self.members("people-ops-approvers") and (self.emp(who) or {}).get("status") == "active"
        return False

    def contractor_expiry(self, subject) -> date | None:
        s = self.emp(subject)
        if not s or s["employment_type"] != "contractor":
            return None
        cap = self.today + timedelta(days=CONTRACTOR_MAX_DAYS)
        return min(day(s["contract_end_date"]), cap) if s.get("contract_end_date") else cap
