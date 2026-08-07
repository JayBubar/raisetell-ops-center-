import requests
import streamlit as st

from config import HUB_BASE_URL, HUB_HEADERS, REPS, TRIGGER_TIMEOUT

st.title("🚀 Triggers")

# ---------------------------------------------------------------------------
# Status strip
# ---------------------------------------------------------------------------
def check(url: str) -> bool:
    try:
        return requests.get(url, timeout=8).status_code == 200
    except requests.exceptions.RequestException:
        return False


def hub_get(route: str, timeout: int = 15):
    try:
        r = requests.get(f"{HUB_BASE_URL}{route}", headers=HUB_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Hub status", "Up" if check(f"{HUB_BASE_URL}/health") else "Down")
with col2:
    bridge_up = check("https://peaceful-generosity-production-312b.up.railway.app/health")
    st.metric("AC ↔ Attio bridge", "Up" if bridge_up else "Down")
with col3:
    snitcher, err = hub_get("/status/snitcher-review")
    st.metric("Snitcher review", snitcher["status_new"] if snitcher else "—",
              help=err or "Entries at Status = New")
with col4:
    sl, sl_err = hub_get("/status/smartlead")
    st.metric("Smartlead leads", (sl or {}).get("total_leads", "—"),
              help=sl_err or "total_leads on the rotation campaign")

st.divider()


def trigger(route: str, params: dict, confirm_text: str = "Run"):
    with st.spinner(f"Calling {route}... (a full batch can take several minutes)"):
        try:
            # TRIGGER_TIMEOUT is deliberately longer than the hub's own
            # subprocess timeout. If this side gave up first, the batch would
            # keep running and mutating Attio with nobody watching the result.
            resp = requests.post(
                f"{HUB_BASE_URL}{route}", headers=HUB_HEADERS, params=params,
                timeout=TRIGGER_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Trigger failed: {e}")
            return

    if payload.get("timed_out"):
        st.warning(f"{confirm_text} — timed out mid-batch. {payload.get('detail', '')}")
    elif payload.get("ok"):
        st.success(f"{confirm_text} — done")
    else:
        st.error(f"{confirm_text} — the script exited with an error")
    if payload.get("stdout_tail"):
        st.code(payload["stdout_tail"], language="text")
    if payload.get("stderr_tail"):
        st.code(payload["stderr_tail"], language="text")


# ---------------------------------------------------------------------------
# Kick off uncontacted outreach from Attio
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Kick off uncontacted outreach from Attio")
    st.caption(
        "Pulls Never Contacted people for one rep, drafts the email "
        "sequence, and builds the task cadence."
    )

    c1, c2 = st.columns(2)
    with c1:
        rep = st.selectbox("Rep", REPS, format_func=lambda r: r.capitalize())
    with c2:
        batch_size = st.number_input("Batch size", min_value=1, max_value=100, value=25)

    if rep == "jay":
        st.caption("Jay's batch also pulls anything still owned by 'Edna Stone'.")

    dry_run = st.checkbox("Dry run first", value=True)

    button_label = "Preview batch" if dry_run else "Kick off uncontacted outreach from Attio"
    if st.button(button_label, type="primary"):
        trigger(
            "/trigger/outreach-batch",
            params={"rep": rep, "batch_size": batch_size, "dry_run": str(dry_run).lower()},
            confirm_text="Outreach batch",
        )

    if not dry_run:
        st.caption(
            "Drafts real emails via Claude, creates real Attio tasks, and "
            "moves contacts to In Outreach — not reversible by re-running."
        )

with st.expander("How re-running is kept safe"):
    st.write(
        "Already-batched contacts are tracked in "
        "`hubspot_email_archive.main.outreach_batch_checkpoint` on MotherDuck, "
        "written one row at a time as each contact's tasks are created. A "
        "crash, a timeout, or a Railway redeploy part-way through a batch "
        "leaves the completed contacts recorded, so the next run skips them "
        "rather than emailing them twice."
    )

st.write("")

# ---------------------------------------------------------------------------
# Cal.com reconciliation (future — placeholder)
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Cal.com ↔ Attio reconciliation")
    st.caption("Daily batch job reconciling per-SDR Cal.com booking links against Attio's Cal Sync.")
    st.button("Run reconciliation", key="cal_recon", disabled=True)
    st.caption("Not built yet")

st.divider()

with st.expander("Why isn't Snitcher discovery a button here?"):
    st.write(
        "It runs as a Cowork/Dispatch scheduled task, not a script in the "
        "hub repo — no API to fire a Dispatch task on demand. Status shows "
        "on the Status page (Snitcher Review queue depth) instead."
    )
