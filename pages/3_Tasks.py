"""
Task Runner — queue mode.

Replaces the earlier task *list*, which reproduced the problem it was meant to
solve: select a task, leave it to read the record, come back, pick the next one.
The fix is not styling. One task fills the screen, its context is already
loaded, and completing it advances in place — the rep never returns to a list.

Context is fetched with the queue, not per card. A round-trip on every advance
would put the wait back exactly where it was taken from.

The AI-drafted email review flow is deliberately absent: shelved as out of
scope, so nothing here touches `outreach_email_drafts`.
"""

from datetime import datetime
import re

import requests
import streamlit as st

from config import HUB_BASE_URL, HUB_HEADERS, REPS

st.set_page_config(page_title="Task Runner", page_icon="✅", layout="wide")

DUE_FILTERS = {
    "all": "All",
    "today": "Today",
    "overdue": "Overdue",
    "upcoming": "Upcoming",
    "none": "No due date",
}
TYPE_FILTERS = {"all": "All", "call": "Call", "followup": "Follow-up", "email": "Email"}

Q = "queue"          # list of task dicts for this session
QI = "queue_index"   # cursor into it
QMETA = "queue_meta" # filter/rep the queue was built with


def hub(method, route, **kw):
    try:
        r = requests.request(method, f"{HUB_BASE_URL}{route}",
                             headers=HUB_HEADERS, timeout=kw.pop("timeout", 120), **kw)
        r.raise_for_status()
        return (r.json() if r.content else {}), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def fmt_dt(value, fmt="%a %d %b %Y"):
    """Attio sends nanosecond precision; fromisoformat only takes six digits."""
    if not value:
        return None
    try:
        cleaned = re.sub(r"\.(\d{6})\d*", r".\1", str(value).replace("Z", "+00:00"))
        return datetime.fromisoformat(cleaned).strftime(fmt)
    except ValueError:
        return str(value)


def reset_queue():
    for k in (Q, QI, QMETA):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Landing view
# ---------------------------------------------------------------------------
if Q not in st.session_state:
    st.title("✅ Task Runner")
    st.caption("Pick a set, then work it one task at a time without going back to a list.")

    c1, c2, c3 = st.columns(3)
    with c1:
        rep = st.selectbox("Rep", REPS, format_func=str.capitalize)
    with c2:
        due = st.selectbox("Due", list(DUE_FILTERS), format_func=DUE_FILTERS.get)
    with c3:
        ttype = st.selectbox("Type", list(TYPE_FILTERS), format_func=TYPE_FILTERS.get)

    if st.button("Start Queue", type="primary"):
        with st.spinner("Loading tasks and their context…"):
            data, err = hub("GET", f"/tasks/{rep}", params={"filter": due, "type": ttype})
        if err:
            st.error(f"Could not reach the hub: {err}")
        elif not data["tasks"]:
            st.warning(f"No **{DUE_FILTERS[due]} / {TYPE_FILTERS[ttype]}** tasks for "
                       f"{rep.capitalize()}.")
            # An empty queue is ambiguous on its own -- say which axis emptied it.
            b, t = data.get("bucket_counts", {}), data.get("type_counts", {})
            st.caption(f"{data['total_open']} open tasks in total · "
                       f"by due: {b or '—'} · by type: {t or '—'}")
            if due != "all" and not b.get(due):
                st.info(
                    f"No task is in the **{DUE_FILTERS[due]}** bucket. Attio tasks in "
                    "this workspace currently have **no deadline set**, so they all "
                    "land in *No due date* — the date filters stay empty until the "
                    "cadence starts writing deadlines. Use **All** meanwhile."
                )
        else:
            st.session_state[Q] = data["tasks"]
            st.session_state[QI] = 0
            st.session_state[QMETA] = {"rep": rep, "due": due, "type": ttype,
                                       "total_open": data["total_open"]}
            st.rerun()
    st.stop()

# ---------------------------------------------------------------------------
# Queue mode
# ---------------------------------------------------------------------------
queue = st.session_state[Q]
idx = st.session_state[QI]
meta = st.session_state[QMETA]

if idx >= len(queue):
    st.title("✅ Queue complete")
    st.success(f"Worked through all {len(queue)} tasks in this session.")
    if st.button("Back to filters", type="primary"):
        reset_queue()
        st.rerun()
    st.stop()

task = queue[idx]
ctx = task.get("context") or {}

head_l, head_r = st.columns([3, 1])
with head_l:
    st.markdown(f"### Task {idx + 1} of {len(queue)}")
    st.caption(f"{meta['rep'].capitalize()} · {DUE_FILTERS[meta['due']]} · "
               f"{TYPE_FILTERS[meta['type']]}")
with head_r:
    if st.button("Exit queue"):
        reset_queue()
        st.rerun()

st.progress((idx) / len(queue))
# Dots stay readable up to ~40; past that the counter above carries it alone.
if len(queue) <= 40:
    st.caption("".join("●" if i < idx else ("◉" if i == idx else "○")
                       for i in range(len(queue))))

st.divider()

left, right = st.columns([3, 2])

# --- The task itself -------------------------------------------------------
with left:
    st.markdown(f"## {task['content']}")
    bits = [b for b in (
        TYPE_FILTERS.get(task["task_type"], task["task_type"]),
        ctx.get("company_name") or task.get("company_name"),
        f"Due {fmt_dt(task['deadline_at'])}" if task.get("deadline_at") else "No due date",
    ) if b]
    st.caption(" · ".join(bits))

    note = None
    outcome = None

    if task["task_type"] == "call":
        phone = ctx.get("phone")
        if phone:
            st.markdown(f"### 📞 [{phone}](tel:{phone.replace(' ', '')})")
        elif not ctx.get("available"):
            # Distinct from "the record has no phone". Collapsing the two sent
            # someone to check a record that did have a number on it.
            st.warning(
                "No linked person record on this task, so no number could be "
                "looked up. Link the task to the contact in Attio."
            )
        else:
            st.warning(
                f"No phone number on {ctx.get('person_name') or 'this record'} "
                "(checked Cell Phone and Phone numbers)."
            )

        opts, opt_err = hub("GET", "/call-outcomes",
                            params={"prospect_path": ctx.get("prospect_path") or ""},
                            timeout=30)
        if opt_err:
            st.error(f"Could not load outcome options: {opt_err}")
        else:
            choices = opts["options"]
            if not choices:
                st.warning(
                    "No call outcomes are configured. Run "
                    "`scripts/setup_call_outcomes.py` to seed the Attio options "
                    "and the `allo_tag_registry` rows that define what each does."
                )
            else:
                outcome = st.radio(
                    "Call outcome", choices, index=None, horizontal=False,
                    key=f"outcome_{task['task_id']}",
                )
                if ctx.get("prospect_path") == "Client":
                    st.caption("Client record — showing maintenance outcomes. These "
                               "are logged and deliberately do not move Prospect Path.")
        st.caption("Allo logs its own call note automatically; nothing here duplicates it.")

    if task["task_type"] == "email":
        if ctx.get("attio_url"):
            st.link_button("Open in Attio →", ctx["attio_url"], type="primary")
            st.caption("Compose from the record page — it sends through the rep's "
                       "own synced Outlook account, so no Graph/Entra setup is needed.")
        else:
            st.warning("No linked person record, so there's nothing to open in Attio.")

    note = st.text_area("Note (optional)", key=f"note_{task['task_id']}",
                        placeholder="Added to the Attio record as a note.")

# --- Context panel ---------------------------------------------------------
with right:
    st.markdown("#### Context")
    if not ctx.get("available"):
        st.info("No linked person record on this task, so there's no context to pull.")
    else:
        who = ctx.get("person_name") or "Unknown contact"
        st.markdown(f"**{who}**")
        meta_bits = [b for b in (ctx.get("company_name"), ctx.get("prospect_path")) if b]
        if meta_bits:
            st.caption(" · ".join(meta_bits))
        if ctx.get("email"):
            st.caption(ctx["email"])
        if ctx.get("attio_url") and task["task_type"] != "email":
            st.link_button("Open in Attio", ctx["attio_url"])

        st.markdown("**Recent notes**")
        if ctx.get("notes"):
            for n in ctx["notes"]:
                with st.container(border=True):
                    st.caption(f"{n.get('title') or 'Note'} · {fmt_dt(n.get('created_at'))}")
                    st.write(n.get("preview") or "_empty_")
        else:
            st.caption("No notes on this record.")

        st.markdown("**Recent emails**")
        if ctx.get("emails"):
            for e in ctx["emails"]:
                arrow = "←" if e.get("direction") == "inbound" else "→"
                st.caption(f"{arrow} {e.get('subject') or '(no subject)'} · "
                           f"{fmt_dt(e.get('sent_at'))}")
            # Not an oversight: Attio's email API returns metadata only and
            # says outright that content is never returned, so there is no
            # preview to show at any price.
            st.caption("_Subject and date only — Attio's API never returns email bodies._")
        else:
            st.caption("No synced emails for this contact.")

        if ctx.get("errors"):
            st.caption("⚠️ " + "; ".join(ctx["errors"]))

st.divider()

# --- Actions ---------------------------------------------------------------
a1, a2, _ = st.columns([1, 1, 3])


def advance():
    st.session_state[QI] += 1


with a1:
    if st.button("Skip", use_container_width=True):
        # Client-side only, by design: the task stays open in Attio and comes
        # back next session. There is nothing to persist.
        advance()
        st.rerun()

with a2:
    if st.button("Complete ✓", type="primary", use_container_width=True):
        if task["task_type"] == "call" and outcome:
            # Outcome and completion go through one route so the task is only
            # closed if the outcome actually landed.
            res, err = hub("POST", f"/tasks/{task['task_id']}/log-call-outcome",
                           params={"record_id": task["linked_record_id"],
                                   "outcome": outcome, "note": note or "",
                                   "complete": "true"}, timeout=60)
        else:
            res, err = hub("PATCH", f"/tasks/{task['task_id']}/complete", timeout=60)

        if err:
            st.error(f"Not completed — {err}")
        elif res and res.get("ok") is False:
            st.error(f"Not completed — {res.get('status')}: {res.get('detail', '')}")
        else:
            if res and res.get("path_changed"):
                st.toast(f"Prospect Path → {res['prospect_path']}")
            advance()
            st.rerun()

if task["task_type"] == "call" and not outcome:
    st.caption("No outcome selected — Complete will close the task without "
               "logging a call outcome.")
