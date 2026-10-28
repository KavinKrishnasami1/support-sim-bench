"""Render a results folder as one self-contained HTML page (view.html).

Every run is shown in full: customer and agent messages, each tool call with its
arguments and result, the grader's checks, and simulator flags pinned to the
message that triggered them. Also `show_run` prints one run to the terminal.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from .report import _pct, load_runs, summarize

CSS = """
:root{--bg:#fbfaf8;--fg:#1d1d1b;--muted:#6b6862;--card:#fff;--line:#e6e2dc;--cust:#eef3fb;--agent:#f3f1ec;
--tool:#f7f6f3;--ok:#1f7a4d;--bad:#b3261e;--warn:#9a5b00;--warnbg:#fff4e0}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe8;--muted:#a19e98;--card:#1f1f1d;--line:#34332f;
--cust:#1d2633;--agent:#26251f;--tool:#1b1b19;--ok:#5cc28f;--bad:#f2786d;--warn:#f0b35a;--warnbg:#33281a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 80px}h1{font-size:22px;margin:0 0 4px}
.muted{color:var(--muted)}table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}th{font-weight:600}
details.run{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:10px 0}
details.run>summary{cursor:pointer;padding:10px 14px;list-style:none;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.badge{font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px;border:1px solid currentColor}
.pass{color:var(--ok)}.fail{color:var(--bad)}.other{color:var(--warn)}
.body{padding:4px 14px 14px}.msg{border-radius:10px;padding:8px 12px;margin:8px 0;white-space:pre-wrap;max-width:85%}
.customer{background:var(--cust)}.agent{background:var(--agent);margin-left:auto}
.who{font-size:12px;color:var(--muted);margin-bottom:2px}
.tool{background:var(--tool);border:1px dashed var(--line);border-radius:8px;padding:6px 10px;margin:6px 0 6px auto;
max-width:85%;font:12px/1.45 ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
.tool.err{border-color:var(--bad)}.flag{background:var(--warnbg);color:var(--warn);border-radius:6px;padding:4px 8px;
font-size:13px;margin:4px 0}.checks li{margin:2px 0}.filters{display:flex;gap:8px;flex-wrap:wrap}
button{font:inherit;padding:4px 10px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
button.on{border-color:var(--fg)}code{font-size:13px}
"""

JS = """
const btns=document.querySelectorAll('[data-filter]');
btns.forEach(b=>b.onclick=()=>{btns.forEach(x=>x.classList.toggle('on',x===b));const f=b.dataset.filter;
document.querySelectorAll('details.run').forEach(d=>{d.style.display=(f==='all'||d.dataset[f]==='1')?'':'none'})});
"""


def _e(s) -> str:
    return html.escape(str(s))


def _run_html(r: dict, user_label: str = "customer") -> str:
    status = "pass" if r["passed"] else ("fail" if r["completed"] else "other")
    label = "PASS" if r["passed"] else ("FAIL" if r["completed"] else r["end_reason"])
    flags_by_event: dict[int, list[dict]] = {}
    for f in r["flags"]:
        flags_by_event.setdefault(f.get("event", -1), []).append(f)
    parts = []
    for i, ev in enumerate(r["events"]):
        if ev["role"] in ("customer", "agent"):
            who = user_label if ev["role"] == "customer" else ev["role"]
            parts.append(f'<div class="msg {ev["role"]}"><div class="who">{who}</div>{_e(ev["text"])}</div>')
        else:
            parts.append(f'<div class="tool{" err" if ev["is_error"] else ""}">{_e(ev["name"])}('
                         f'{_e(json.dumps(ev["args"]))})\n→ {_e(json.dumps(ev["result"])[:1200])}</div>')
        for f in flags_by_event.get(i, []):
            parts.append(f'<div class="flag">⚑ {_e(f["type"])}: {_e(f.get("match", ""))}</div>')
    for f in flags_by_event.get(-1, []):
        parts.append(f'<div class="flag">⚑ {_e(f["type"])}: {_e(f.get("explanation", ""))}</div>')
    checks = ""
    if r["grade"]:
        items = "".join(f'<li class="{"pass" if c["ok"] else "fail"}">{"✓" if c["ok"] else "✗"} <code>{_e(c["check"])}</code>'
                        + ("" if c["ok"] else f' <span class="muted">expected {_e(json.dumps(c.get("expected", c.get("detail"))))}'
                                              f' / actual {_e(json.dumps(c.get("actual", "")))}</span>') + "</li>"
                        for c in r["grade"]["checks"])
        checks = f'<h4>Grader</h4><ul class="checks">{items}</ul>'
        svs = r["grade"].get("security_violations", [])
        if svs:
            checks += ('<h4 class="fail">Security violations</h4><ul class="checks">'
                       + "".join(f'<li class="fail"><code>{_e(v["code"])}</code> '
                                 f'{"step " + str(v["step"]) + " · " if v.get("step") is not None else ""}{_e(v["detail"])}</li>'
                                 for v in svs) + "</ul>")
    err = f'<p class="fail">Error: {_e(r["error"])}</p>' if r.get("error") else ""
    n_sv = len((r.get("grade") or {}).get("security_violations", []))
    sv_badge = f'<span class="badge fail">⚠ security ×{n_sv}</span>' if n_sv else ""
    return (f'<details class="run" data-fail="{int(r["completed"] and not r["passed"])}" data-flagged="{int(bool(r["flags"]))}" '
            f'data-sv="{int(bool(n_sv))}">'
            f'<summary><span class="badge {status}">{_e(label)}</span>{sv_badge}<b>{_e(r["task_id"])}</b> trial {r["trial"]}'
            f'<span class="muted">{r["customer_turns"]} {user_label} turns · ${r["cost_usd"]:.3f} · ended: {_e(r["end_reason"])}'
            f'{" · ⚑ " + str(len(r["flags"])) if r["flags"] else ""}</span></summary>'
            f'<div class="body">{err}{"".join(parts)}{checks}</div></details>')


def render(run_dir: Path) -> Path:
    s = summarize(run_dir)
    runs = sorted(load_runs(run_dir), key=lambda r: (r["task_id"], r["trial"]))
    c = s["config"]
    k = s["k"]
    v3 = c.get("suite") == "v3"
    user_label = "employee" if v3 else "customer"
    head = "".join(f"<th>pass^{j}</th>" for j in range(1, k + 1)) + ("<th>Security violations</th>" if v3 else "")
    rows = "".join(f'<tr><td>{tid}</td><td>{t["n"]}</td><td>{t["passed"]}</td>'
                   + "".join(f"<td>{_pct(t[f'pass^{j}'])}</td>" for j in range(1, k + 1))
                   + (f'<td>{t.get("sv_runs", 0)}</td>' if v3 else "")
                   + f'<td>{t["flagged_runs"]}</td></tr>' for tid, t in s["tasks"].items())
    total = (f'<tr><th>All</th><th>{s["graded_runs"]}</th><th></th>'
             + "".join(f"<th>{_pct(s['overall'][f'pass^{j}'])}</th>" for j in range(1, k + 1))
             + (f'<th>{_pct(s["overall"].get("security_violation_rate"))}</th>' if v3 else "")
             + f'<th>{s["flagged_runs"]}</th></tr>')
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Support sim runs</title><style>{CSS}</style></head>
<body><main><h1>{_e(c.get("agent_model"))} as agent</h1>
<p class="muted">{user_label.capitalize()} simulator {_e(c.get("user_model"))} · k={k} · {s["graded_runs"]}/{s["runs"]} runs graded ·
cost ${s["cost_usd"]:.2f} · end reasons {_e(s["end_reasons"])}</p>
<table><tr><th>Task</th><th>Trials</th><th>Passed</th>{head}<th>Flagged</th></tr>{rows}{total}</table>
<div class="filters"><button class="on" data-filter="all">All runs</button><button data-filter="fail">Failed</button>
<button data-filter="flagged">Flagged simulator</button>{'<button data-filter="sv">Security violations</button>' if v3 else ""}</div>
{"".join(_run_html(r, user_label) for r in runs)}
</main><script>{JS}</script></body></html>"""
    out = run_dir / "view.html"
    out.write_text(page)
    return out


def show_run(path: Path) -> None:
    r = json.loads(path.read_text())
    print(f"{r['task_id']} trial {r['trial']}: {'PASS' if r['passed'] else 'FAIL'} ({r['end_reason']})\n")
    for i, ev in enumerate(r["events"]):
        if ev["role"] == "tool":
            print(f"    [{ev['name']}] {json.dumps(ev['args'])} -> {json.dumps(ev['result'])[:200]}")
        else:
            print(f"{ev['role'].upper():>8}: {ev['text']}")
        for f in r["flags"]:
            if f.get("event") == i:
                print(f"    !! FLAG {f['type']}: {f.get('match', '')}")
    if r["grade"]:
        print("\nchecks: " + ", ".join(f"{c['check']}={'ok' if c['ok'] else 'FAIL'}" for c in r["grade"]["checks"]))
        for v in r["grade"].get("security_violations", []):
            print(f"  SECURITY {v['code']}: {v['detail']}")
