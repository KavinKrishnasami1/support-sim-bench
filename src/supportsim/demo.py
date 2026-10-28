"""Static demo pages: one page per saved run, plus an index.

Each run page shows the task scenario and the policy sections it depends on, the conversation as chat bubbles with
every tool call as a collapsible card between messages, and the grader's verdict: expected versus actual database
changes and every check. The index has the results tables and the grader self-test summary.

Everything is plain HTML with inline CSS: no scripts, no network requests, so the pages open as local files.
  supportsim demo --run results/<dir>/runs/X12_trial0.json --run ... --results results/<dir> ... --out demo
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from pathlib import Path

from .tasks import check_task, load_tasks
from .tools import WRITE_TOOLS
from .world import SUITES, policy_text

MODEL_NAMES = {"claude-haiku-5-5": "Haiku 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-opus-5-5": "Opus 5.5"}
CHECK_LABELS = {
    "state.refunds": "Card refunds match exactly",
    "state.credits": "Account credits match exactly",
    "state.order_changes": "Order changes match (status, address)",
    "state.escalations": "Escalations match (order and reason)",
    "state.replacements": "Replacement orders match",
    "verify_first": "Identity verified before every write",
    "escalation_ids": "Every escalation identifies its order",
    "credit_cap": "Credit stays within the conversation limit",
}

CSS = """
:root{--bg:#fbfaf7;--card:#ffffff;--ink:#1d1d1b;--muted:#5d5b55;--line:#dedbd3;--cust:#eef2f8;--agent:#f3f0e8;
--tool:#f7f6f2;--write:#fff5e6;--writeline:#e3b05a;--pass:#1f7a46;--passbg:#e7f4ec;--fail:#b3261e;--failbg:#fbeaea;
--accent:#3b5bab;--code:#f1efe9}
@media (prefers-color-scheme:dark){:root{--bg:#181816;--card:#22221f;--ink:#ecebe6;--muted:#a9a69d;--line:#3a3934;
--cust:#26303f;--agent:#2d2a23;--tool:#23231f;--write:#3a2f1c;--writeline:#b8893d;--pass:#7fd3a0;--passbg:#1c3326;
--fail:#f2a19b;--failbg:#3d2120;--accent:#9db4ef;--code:#2b2a26}}
*{box-sizing:border-box}
html{font-size:112.5%}
body{margin:0;background:var(--bg);color:var(--ink);font:1rem/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
"Helvetica Neue",Arial,sans-serif}
main{max-width:56rem;margin:0 auto;padding:1.5rem 1rem 4rem}
h1{font-size:1.75rem;line-height:1.25;margin:.25rem 0 .5rem}
h2{font-size:1.3rem;margin:2.5rem 0 .75rem;padding-bottom:.35rem;border-bottom:2px solid var(--line)}
h3{font-size:1.05rem;margin:1.25rem 0 .4rem}
p{margin:.5rem 0}
a{color:var(--accent)}
.muted{color:var(--muted)}
.crumb{font-size:.9rem}
.badge{display:inline-block;font-weight:700;padding:.15rem .6rem;border-radius:.4rem;font-size:.95rem}
.pass{color:var(--pass);background:var(--passbg)} .fail{color:var(--fail);background:var(--failbg)}
.card{background:var(--card);border:1px solid var(--line);border-radius:.6rem;padding:1rem 1.15rem;margin:.75rem 0}
.callout{border-left:5px solid var(--fail);background:var(--failbg)}
.callout.ok{border-left-color:var(--pass);background:var(--passbg)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:.35rem 1rem;margin:.25rem 0}
dt{font-weight:600;color:var(--muted)} dd{margin:0}
@media (max-width:40rem){dl{grid-template-columns:1fr} dt{margin-top:.4rem}}
ul{margin:.3rem 0 .3rem 1.2rem;padding:0} li{margin:.15rem 0}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.88em}
code{background:var(--code);padding:.05rem .3rem;border-radius:.25rem}
pre{background:var(--code);padding:.75rem;border-radius:.4rem;overflow-x:auto;white-space:pre-wrap;word-break:break-word;margin:.4rem 0}
.policy h4{font-size:1rem;margin:1rem 0 .25rem}
.tablewrap{overflow-x:auto;margin:.5rem 0}
table{border-collapse:collapse;width:100%;font-size:.95rem}
th,td{border-bottom:1px solid var(--line);padding:.45rem .6rem;text-align:left;vertical-align:top}
th{font-weight:600;color:var(--muted)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
li.cont{list-style:none}
.chat{display:flex;flex-direction:column;gap:.6rem}
.msg{max-width:85%;padding:.7rem .95rem;border-radius:1rem;border:1px solid var(--line)}
.msg .who{font-size:.8rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:var(--muted);margin-bottom:.15rem}
.msg.customer{align-self:flex-start;background:var(--cust);border-bottom-left-radius:.3rem}
.msg.agent{align-self:flex-end;background:var(--agent);border-bottom-right-radius:.3rem}
.msg p{margin:.3rem 0}
details.tool{align-self:stretch;margin:0 1.5rem;background:var(--tool);border:1px dashed var(--line);border-radius:.5rem}
details.tool.write{background:var(--write);border:1px solid var(--writeline)}
details.tool>summary{cursor:pointer;padding:.45rem .8rem;font-size:.92rem}
details.tool>div{padding:0 .8rem .6rem}
details.tool .err{color:var(--fail);font-weight:600}
summary .tag{font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;margin-right:.4rem;color:var(--muted)}
details.tool.write summary .tag{color:var(--writeline)}
.ok-mark{color:var(--pass);font-weight:700} .bad-mark{color:var(--fail);font-weight:700}
tr.bad td{background:var(--failbg)}
footer{margin-top:3rem;font-size:.85rem;color:var(--muted)}
"""


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def money(x) -> str:
    return f"${x:,.2f}" if abs(x) >= 0.01 or x == 0 else f"${x:.3f}"


# --- a small Markdown renderer for the policy text and chat messages (headings, lists, tables, bold, code) ---
def _inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", s)
    return s


def md(text: str) -> str:
    out, para, lines, i = [], [], text.splitlines(), 0

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush(); i += 1; continue
        if line.startswith("#"):
            flush()
            out.append(f"<h4>{_inline(line.lstrip('#').strip())}</h4>"); i += 1; continue
        if line.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            out.append('<div class="tablewrap"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>"
                                                          for r in body) + "</tbody></table></div>")
            continue
        m = re.match(r"(\s*)(?:[-*]|\d+\.)\s+(.*)", line)
        if m:
            flush()
            items = []  # [indent, text, is_continuation]
            while i < len(lines):
                m = re.match(r"(\s*)(?:[-*]|\d+\.)\s+(.*)", lines[i])
                if m:
                    items.append([len(m.group(1)), m.group(2), False])
                elif lines[i].strip() and lines[i].startswith(" ") and items:
                    ind = len(lines[i]) - len(lines[i].lstrip())
                    if ind > items[-1][0]:  # wraps the item above
                        items[-1][1] += " " + lines[i].strip()
                    else:  # text that belongs to a parent item, after its sub-list
                        items.append([max(ind - 2, 0), lines[i].strip(), True])
                else:
                    break
                i += 1
            depth, html_ = [], []
            for ind, txt, cont in items:
                while depth and ind < depth[-1]:
                    html_.append("</li></ul>"); depth.pop()
                if not depth or ind > depth[-1]:
                    html_.append("<ul>"); depth.append(ind)
                else:
                    html_.append("</li>")
                html_.append(('<li class="cont">' if cont else "<li>") + _inline(txt))
            html_.append("</li></ul>" * len(depth))
            out.append("".join(html_))
            continue
        para.append(line.strip()); i += 1
    flush()
    return "\n".join(out)


def policy_sections(suite: str, numbers: list[int]) -> str:
    text = policy_text(suite)
    parts = re.split(r"(?m)^## ", text)
    picked = [p for p in parts[1:] if int(p.split(".", 1)[0]) in numbers]
    return "\n".join(md("## " + p) for p in picked)


# --- run pages ---
def _tool_card(e: dict) -> str:
    name, args, res = e["name"], e.get("args", {}), e.get("result", {})
    write = name in WRITE_TOOLS
    kind = "write" if write else "verify" if name == "verify_identity" else "lookup"
    key = {k: v for k, v in args.items() if k in ("order_id", "customer_id", "amount", "reason", "status", "restaurant_id")}
    brief = ", ".join(f"{k}={money(v) if k == 'amount' else v}" for k, v in key.items())
    err = '<span class="err"> error</span>' if e.get("is_error") else ""
    return (f'<details class="tool{" write" if write else ""}"><summary><span class="tag">{kind}'
            f'</span><code>{esc(name)}</code> <span class="muted">{esc(brief)}</span>{err}</summary><div>'
            f'<h3>Arguments</h3><pre>{esc(json.dumps(args, indent=2))}</pre>'
            f'<h3>Result</h3><pre>{esc(json.dumps(res, indent=2))}</pre></div></details>')


def _fmt(kind: str, v) -> str:
    if kind in ("refunds", "credits"):
        return money(v)
    if isinstance(v, (list, tuple)):
        return " · ".join(map(str, v))
    if isinstance(v, dict):
        return ", ".join(f"{k}: {x}" for k, x in v.items())
    return str(v)


def _changes_table(grade: dict) -> str:
    rows = []
    for c in grade["checks"]:
        if not c["check"].startswith("state."):
            continue
        kind = c["check"].split(".", 1)[1]
        exp, act = c.get("expected"), c.get("actual")
        if isinstance(exp, dict):
            for k in sorted(set(exp) | set(act or {})):
                e, a = exp.get(k), (act or {}).get(k)
                rows.append((kind, k, _fmt(kind, e) if e is not None else "none", _fmt(kind, a) if a is not None else "none",
                             e == a if not isinstance(e, float) else a is not None and abs(e - a) < 0.011))
        else:  # escalations / replacements: lists of tuples
            exp_s = [" / ".join(map(str, x)) if isinstance(x, (list, tuple)) else str(x) for x in exp or []]
            act_s = [" / ".join(map(str, x)) if isinstance(x, (list, tuple)) else str(x) for x in act or []]
            if exp_s or act_s:
                rows.append((kind, "(order / reason)" if kind == "escalations" else "(order / items)",
                             "<br>".join(map(esc, exp_s)) or "none", "<br>".join(map(esc, act_s)) or "none", c["ok"]))
                continue
    if not rows:
        return '<p class="muted">The correct outcome changes nothing in the database, and nothing was changed.</p>'
    body = "".join(
        f'<tr class="{"" if ok else "bad"}"><td>{esc(kind)}</td><td><code>{esc(k)}</code></td>'
        f'<td class="num">{e if "<br>" in str(e) else esc(e)}</td><td class="num">{a if "<br>" in str(a) else esc(a)}</td>'
        f'<td>{"<span class=ok-mark>✓ match</span>" if ok else "<span class=bad-mark>✗ differs</span>"}</td></tr>'
        for kind, k, e, a, ok in rows)
    return ('<div class="tablewrap"><table><thead><tr><th>Change</th><th>Record</th><th class="num">Expected</th>'
            f'<th class="num">Actual</th><th></th></tr></thead><tbody>{body}</tbody></table></div>')


def _checks_list(grade: dict) -> str:
    items = []
    for c in grade["checks"]:
        label = CHECK_LABELS.get(c["check"], c["check"].replace("required:", "Required call: ").replace("forbidden:", "Forbidden call: "))
        items.append(f'<li>{"<span class=ok-mark>✓</span>" if c["ok"] else "<span class=bad-mark>✗</span>"} {esc(label)}'
                     f' <span class="muted">(<code>{esc(c["check"])}</code>)</span></li>')
    return "<ul style='list-style:none;margin-left:0'>" + "".join(items) + "</ul>"


def _diff_sentences(grade: dict) -> list[str]:
    out = []
    for c in grade["checks"]:
        if c["ok"] or not c["check"].startswith("state.") or not isinstance(c.get("expected"), dict):
            continue
        kind = c["check"].split(".", 1)[1]
        exp, act = c["expected"], c.get("actual") or {}
        for k in sorted(set(exp) | set(act)):
            e, a = exp.get(k, 0), act.get(k, 0)
            if isinstance(e, (int, float)) and abs(e - a) >= 0.011:
                what = "credit to customer" if kind == "credits" else "refund on order"
                out.append(f"Expected {money(e)} {what} {k}; the agent gave {money(a)} ({'+' if a > e else '−'}"
                           f"{money(abs(a - e))}).")
    return out


def page(run: dict, task: dict, model: str, run_path: str, note: str | None) -> str:
    u, g = task["user"], run["grade"]
    passed = run["passed"]
    verdict = f'<span class="badge {"pass" if passed else "fail"}">{"PASS" if passed else "FAIL"}</span>'
    who = MODEL_NAMES.get(model, model)
    chat = []
    for e in run["events"]:
        if e["role"] in ("customer", "agent"):
            text = (e.get("text") or "").replace("###STOP###", "").strip()
            if text:
                chat.append(f'<div class="msg {e["role"]}"><div class="who">{"Customer (simulated)" if e["role"] == "customer" else "Agent · " + esc(who)}</div>{md(text)}</div>')
        elif e["role"] == "tool":
            chat.append(_tool_card(e))
    diffs = _diff_sentences(g)
    summary_box = (f'<div class="card callout ok"><strong>Passed.</strong> The final database matches the correct '
                   f'outcome exactly and every check passed.</div>' if passed else
                   '<div class="card callout"><strong>Failed.</strong> ' +
                   " ".join(esc(d) for d in diffs) + (f"<p>{esc(note)}</p>" if note else "") + "</div>")
    facts = "".join(f"<li>{esc(f)}</li>" for f in u["facts"])
    reveal = "".join(f"<li>{esc(f)}</li>" for f in u.get("reveal_rules", []) + u.get("behaviors", []))
    flags = "".join(f"<li>{esc(f['type'])}: {esc(f.get('explanation') or f.get('detail') or '')}</li>" for f in run.get("flags", []))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(task['id'])} · {esc(who)} · {"pass" if passed else "fail"}</title><style>{CSS}</style></head><body><main>
<p class="crumb"><a href="index.html">← All results</a></p>
<p class="muted">support-sim-bench {esc(task.get('suite', ''))} · task {esc(task['id'])} · agent {esc(who)} · trial {run.get('trial', 0) + 1}</p>
<h1>{esc(task['title'])} {verdict}</h1>
{summary_box}

<h2>The scenario</h2>
<div class="card"><dl>
<dt>Customer</dt><dd>{esc(u['persona'])}</dd>
<dt>What happened</dt><dd>{esc(u['situation'])}</dd>
<dt>What they want</dt><dd>{esc(u['goal'])}</dd>
<dt>Why it's hard</dt><dd>{esc(task['tricky'])}</dd>
<dt>Correct outcome</dt><dd><strong>{esc(task['resolution_summary'])}</strong></dd>
</dl></div>
<details class="card"><summary><strong>What the simulated customer knows</strong> <span class="muted">(hidden from the agent)</span></summary>
<h3>Facts</h3><ul>{facts}</ul><h3>When to reveal them, and how to behave</h3><ul>{reveal}</ul></details>

<h2>The policy that applies</h2>
<p class="muted">The agent gets the whole policy ({len(re.findall(r"(?m)^## ", policy_text(task.get('suite', 'v1'))))} sections). These are the sections this task depends on.</p>
<div class="card policy">{policy_sections(task.get('suite', 'v1'), task.get('policy_sections', []))}</div>

<h2>The conversation</h2>
<p class="muted">Customer messages on the left, agent on the right. Grey cards are lookups and identity checks; amber
cards are writes that change the database. Click a card to see the call and what the tool returned.</p>
<div class="chat">{''.join(chat)}</div>

<h2>The grader</h2>
<p>{verdict} The grader never reads the agent's wording. It compares the database the agent left behind with the
correct outcome, and checks the order of actions.</p>
<h3>Database changes: expected versus actual</h3>
{_changes_table(g)}
<h3>Checks</h3>
{_checks_list(g)}
{f'<h3>Simulator flags</h3><ul>{flags}</ul>' if flags else ''}
<footer>Source: <code>{esc(run_path)}</code> · cost {money(run.get('cost_usd') or 0)} · {run.get('customer_turns', '?')} customer turns.
Generated by <code>supportsim demo</code>; no scripts or network requests.</footer>
</main></body></html>"""


# --- index ---
def _collect(results_dirs: list[Path]) -> dict:
    """{suite: {model: {task_id: [passed, ...]}}}; a later folder replaces an earlier one's runs of the same task."""
    out: dict = defaultdict(lambda: defaultdict(dict))
    for d in results_dirs:
        cfg = json.loads((d / "config.json").read_text())
        by_task = defaultdict(list)
        for p in sorted((d / "runs").glob("*.json")):
            r = json.loads(p.read_text())
            if r.get("completed"):
                by_task[r["task_id"]].append(r["passed"])
        for t, v in by_task.items():
            out[cfg.get("suite", "v1")][cfg["agent_model"]][t] = v
    return out


def index(results_dirs: list[Path], pages: list[tuple[str, str, str]]) -> str:
    data = _collect(results_dirs)
    models = [m for m in MODEL_NAMES if any(m in data[s] for s in data)]
    # headline: suite x model
    head = "".join(f"<th class='num'>{esc(MODEL_NAMES[m])}</th>" for m in models)
    rows = []
    for s in sorted(data):
        cells = []
        for m in models:
            runs = [x for v in data[s].get(m, {}).values() for x in v]
            cells.append(f"<td class='num'>{100 * sum(runs) / len(runs):.0f}% <span class='muted'>({sum(runs)}/{len(runs)})</span></td>"
                         if runs else "<td class='num muted'>not run</td>")
        rows.append(f"<tr><td><strong>{esc(s)}</strong> <span class='muted'>{len(load_tasks(suite=s))} tasks</span></td>{''.join(cells)}</tr>")
    headline = f"<div class='tablewrap'><table><thead><tr><th>Suite</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    # v3food per task
    v3 = data.get("v3food", {})
    tasks = {t["id"]: t for t in load_tasks(suite="v3food")} if "v3food" in data else {}
    trows = []
    for tid, t in tasks.items():
        cells = []
        for m in models:
            v = v3.get(m, {}).get(tid)
            if v is None:
                cells.append("<td class='num muted'>·</td>")
            else:
                cls = "ok-mark" if all(v) else "bad-mark"
                cells.append(f"<td class='num'><span class='{cls}'>{sum(v)}/{len(v)}</span></td>")
        trows.append(f"<tr><td><code>{tid}</code></td><td>{esc(t['title'])}</td>{''.join(cells)}</tr>")
    per_task = (f"<div class='tablewrap'><table><thead><tr><th>Task</th><th>Scenario</th>{head}</tr></thead>"
                f"<tbody>{''.join(trows)}</tbody></table></div>")
    # self-test
    st = []
    for s in SUITES:
        ts = load_tasks(suite=s)
        problems = [p for t in ts for p in check_task(t)]
        n_m = sum(len(t.get("mistakes", [])) for t in ts)
        st.append(f"<tr><td><strong>{s}</strong></td><td class='num'>{len(ts)}</td><td class='num'>{n_m}</td>"
                  f"<td>{'<span class=ok-mark>✓ every correct solution passes, every wrong one fails</span>' if not problems else '<span class=bad-mark>✗ ' + str(len(problems)) + ' problems</span>'}</td></tr>")
    selftest = ("<div class='tablewrap'><table><thead><tr><th>Suite</th><th class='num'>Correct solutions</th>"
                "<th class='num'>Known-wrong solutions</th><th>Result</th></tr></thead><tbody>" + "".join(st) + "</tbody></table></div>")
    links = "".join(f'<li><a href="{esc(f)}"><strong>{esc(title)}</strong></a><br><span class="muted">{esc(desc)}</span></li>'
                    for f, title, desc in pages)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>support-sim-bench results</title><style>{CSS}</style></head><body><main>
<h1>support-sim-bench</h1>
<p>A multi-turn benchmark for AI customer-support agents. An agent with tools and a written policy handles
food-delivery support chats with a simulated customer, and each run is graded on the database it leaves behind,
never on its wording.</p>

<h2>Two runs, side by side</h2>
<p class="muted">The same task, X12: a promo order with two missing items, where the customer wants one refunded to the
card and the other as credit.</p>
<ul style="list-style:none;margin-left:0">{links}</ul>

<h2>Results by suite</h2>
<p class="muted">Share of graded runs that passed. v1 and v2: 3 trials per task. v3food (the food-delivery v3): 1 trial per task for Haiku and
Sonnet; Opus ran the 16 core tasks once and the 6 scale tasks 5 times each.</p>
{headline}

<h2>v3food, task by task</h2>
<p class="muted">Passed / runs. X08 was merged into X07 during design.</p>
{per_task}

<h2>Grader self-test</h2>
<p>Before any model runs, every task's correct solution is replayed through the real tools and grader (it must pass),
along with named wrong solutions (each must fail). Re-run live when this page was generated.</p>
{selftest}
<footer>Generated by <code>supportsim demo</code>. Static HTML: no scripts, no network requests.</footer>
</main></body></html>"""


def build(run_specs: list[tuple[Path, str | None]], results_dirs: list[Path], out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    pages, written = [], []
    for run_path, note in run_specs:
        run = json.loads(run_path.read_text())
        cfg = json.loads((run_path.parent.parent / "config.json").read_text())
        suite, model = cfg.get("suite", "v1"), cfg["agent_model"]
        task = next(t for t in load_tasks(suite=suite) if t["id"] == run["task_id"])
        name = f"{run['task_id']}-{model.replace('claude-', '')}-{'pass' if run['passed'] else 'fail'}.html"
        (out / name).write_text(page(run, task, model, str(run_path), note))
        written.append(out / name)
        verdict = "passes" if run["passed"] else "fails"
        pages.append((name, f"{task['id']} · {MODEL_NAMES.get(model, model)} {verdict}",
                      task["title"] + (f". {note}" if note else "")))
    (out / "index.html").write_text(index(results_dirs, pages))
    written.append(out / "index.html")
    return written
