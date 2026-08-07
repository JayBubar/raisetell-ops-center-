import re
from datetime import datetime

import requests
import streamlit as st

from config import HUB_BASE_URL, HUB_HEADERS, REPS

st.title("✅ Task Runner")
st.caption(
    "Open Attio tasks with their AI-drafted email content shown inline — "
    "the reason reps don't need to open Attio just to work a cadence."
)

rep = st.selectbox("Rep", REPS, format_func=lambda r: r.capitalize())

# Tasks live in session_state rather than a local variable. Every button on
# this page triggers a Streamlit rerun, and a rerun re-evaluates the whole
# script with the "Load" button back to False -- so holding the list in a
# local would empty it the moment you completed or drafted anything.
state_key = f"tasks_{rep}"


def format_due(deadline: str | None) -> str:
    """Attio returns deadlines as ISO strings with nanosecond precision
    ("2026-07-09T08:00:00.000000000Z"), which is unreadable in a list.
    fromisoformat can't parse 9-digit fractional seconds, so trim to micro."""
    if not deadline:
        return "no due date"
    try:
        cleaned = re.sub(r"\.(\d{6})\d*", r".\1", deadline.replace("Z", "+00:00"))
        return datetime.fromisoformat(cleaned).strftime("%a %d %b %Y")
    except ValueError:
        return deadline


def load_tasks():
    try:
        resp = requests.get(f"{HUB_BASE_URL}/tasks/{rep}", headers=HUB_HEADERS, timeout=60)
        resp.raise_for_status()
        st.session_state[state_key] = resp.json()
    except requests.exceptions.RequestException as e:
        st.session_state[state_key] = []
        st.error(f"Could not reach hub: {e}")


c1, c2 = st.columns([1, 4])
with c1:
    if st.button("Load open tasks", type="primary"):
        load_tasks()
with c2:
    if state_key in st.session_state and st.button("Refresh"):
        load_tasks()

tasks = st.session_state.get(state_key)

if tasks is None:
    st.info("Press **Load open tasks** to pull this rep's cadence.")
elif not tasks:
    st.info("No open tasks for this rep.")

for t in tasks or []:
    task_id = t["task_id"]
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{t['content']}**")
            # Only cadence tasks carry a company; don't leave a dangling
            # separator on the hand-written ones.
            bits = [f"Due {format_due(t.get('deadline_at'))}"]
            if t.get("company_name"):
                bits.append(t["company_name"])
            st.caption(" · ".join(bits))
        with col2:
            if st.button("Mark complete", key=f"complete_{task_id}"):
                try:
                    r = requests.patch(
                        f"{HUB_BASE_URL}/tasks/{task_id}/complete",
                        headers=HUB_HEADERS, timeout=30,
                    )
                    r.raise_for_status()
                except requests.exceptions.RequestException as e:
                    st.error(f"Could not complete task: {e}")
                else:
                    # Drop it locally so the list updates without a full reload.
                    st.session_state[state_key] = [
                        x for x in st.session_state[state_key] if x["task_id"] != task_id
                    ]
                    st.rerun()

        if t.get("draft"):
            subject = st.text_input("Subject", value=t["draft"]["subject"], key=f"subj_{task_id}")
            body = st.text_area("Body", value=t["draft"]["body"], key=f"body_{task_id}", height=140)

            if st.button("Create Outlook draft", key=f"draft_{task_id}"):
                try:
                    r = requests.post(
                        f"{HUB_BASE_URL}/tasks/{task_id}/draft-email",
                        headers=HUB_HEADERS,
                        params={"rep": rep, "subject": subject, "body": body},
                        timeout=60,
                    )
                    r.raise_for_status()
                    result = r.json()
                except requests.exceptions.RequestException as e:
                    detail = ""
                    if e.response is not None:
                        detail = e.response.text[:300]
                        if e.response.status_code == 428:
                            detail = (
                                f"{rep.capitalize()} hasn't connected Outlook yet — "
                                "see the Status page."
                            )
                    st.error(f"Draft creation failed. {detail}")
                else:
                    st.success(f"Draft created in {result['mailbox']} → {result['to']}")
                    if result.get("web_link"):
                        st.markdown(f"[Open in Outlook]({result['web_link']})")

            st.caption(
                "Creates a draft in the rep's own mailbox. You press Send in "
                "Outlook — Attio's mail-sync logs it on the contact from there. "
                "Edits here aren't written back to MotherDuck."
            )

        # Left-a-VM tasks exist alongside the Call task by design, meant to
        # be skipped here if the call actually connects.
        if "Left a VM" in t["content"]:
            st.caption("Skip this if the call actually connected.")
            if st.button("Skip (call connected)", key=f"skip_{task_id}"):
                try:
                    r = requests.patch(
                        f"{HUB_BASE_URL}/tasks/{task_id}/complete",
                        headers=HUB_HEADERS, timeout=30,
                    )
                    r.raise_for_status()
                except requests.exceptions.RequestException as e:
                    st.error(f"Could not skip task: {e}")
                else:
                    st.session_state[state_key] = [
                        x for x in st.session_state[state_key] if x["task_id"] != task_id
                    ]
                    st.rerun()

st.divider()
with st.expander("Known limitations"):
    st.write(
        "- Subject/body edits here are sent to Outlook but not written back "
        "to `outreach_email_drafts` — reload and you'll see the original draft\n"
        "- Each rep must complete the Microsoft sign-in once before "
        "**Create Outlook draft** works (Status page shows who has)\n"
        "- Task list is fetched unfiltered from Attio and filtered by "
        "assignee in the hub; if task volume grows a lot this wants a "
        "server-side filter"
    )
