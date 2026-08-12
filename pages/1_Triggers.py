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
    # Was a hardcoded probe of peaceful-generosity-production-312b, a host that
    # 404s and that the bridge never ran on -- so this tile read "Down" no
    # matter what the bridge was doing. The bridge is a route inside the hub;
    # the honest headline is when it last actually received an event, since a
    # mounted route with a mis-wired AC automation looks healthy from outside.
    bridge, bridge_err = hub_get("/status/ac-bridge")
    if bridge_err:
        st.metric("AC bridge · last event", "—", help=bridge_err)
    elif not bridge.get("route_registered"):
        st.metric("AC bridge · last event", "Not mounted",
                  help=f"POST {bridge.get('webhook_path')} is not registered on the hub")
    else:
        ev = bridge.get("events") or {}
        if not ev.get("available"):
            st.metric("AC bridge · last event", "Unknown",
                      help=f"Receiver is mounted; webhook log unreadable: {ev.get('reason', '')}")
        elif ev.get("last_event_at"):
            st.metric("AC bridge · last event", ev["last_event_at"][:10],
                      help=f"{ev.get('events_7d', 0)} events in the last 7 days. "
                           "Receiver is mounted.")
        else:
            st.metric("AC bridge · last event", "None yet",
                      help="Receiver is mounted but has logged no events. "
                           "Quiet is normal if no tags changed.")
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

# ---------------------------------------------------------------------------
# Automation flags -- pause/resume without a redeploy
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("Automation flags")
    st.caption(
        "Read and written through the hub's `/config/flags`, which stores them "
        "in MotherDuck. `outreach_rotation.py` reads the flag once at the start "
        "of each run, so a change here takes effect on the next scheduled run — "
        "no code edit, no redeploy."
    )

    def apply_flag(key: str):
        """Runs on toggle. On failure the switch is snapped back, so the UI
        never shows a state the scheduled job won't actually obey."""
        desired = st.session_state[f"flag_{key}"]
        try:
            r = requests.patch(
                f"{HUB_BASE_URL}/config/flags/{key}",
                headers=HUB_HEADERS,
                params={"value": str(desired).lower(), "updated_by": "ops-center"},
                timeout=30,
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            st.session_state[f"flag_{key}"] = not desired
            st.session_state[f"flag_err_{key}"] = str(e)
        else:
            st.session_state.pop(f"flag_err_{key}", None)

    flags, flags_err = hub_get("/config/flags")

    if flags_err:
        st.error(f"Could not read flags from the hub: {flags_err}")
    elif not flags:
        st.info("The hub reports no toggleable flags.")
    else:
        if st.button("Refresh from hub", key="flags_refresh"):
            # Widget state wins over the fetched value once a toggle exists, so
            # a flag changed elsewhere (or straight in MotherDuck) would keep
            # rendering stale here until these keys are dropped.
            for f in flags:
                st.session_state.pop(f"flag_{f['key']}", None)
            st.rerun()

        for f in flags:
            key = f["key"]
            skey = f"flag_{key}"
            if skey not in st.session_state:
                st.session_state[skey] = bool(f["value"])

            st.toggle(f["label"], key=skey, on_change=apply_flag, args=(key,))
            st.caption(f["description"])

            if st.session_state.get(f"flag_err_{key}"):
                st.error(
                    "Toggle not saved — the hub rejected the write, so the "
                    f"scheduled job still uses the old value. {st.session_state[f'flag_err_{key}']}"
                )

            # `source` is the honest part: "default" is also what a MotherDuck
            # outage looks like, so don't render it as a stored value.
            source = f.get("source")
            if source == "motherduck":
                who = f.get("updated_by") or "unknown"
                when = (f.get("updated_at") or "")[:19].replace("T", " ")
                st.caption(f"Stored in MotherDuck · set by {who}" + (f" · {when} UTC" if when else ""))
            elif source == "env":
                st.caption(
                    "Value is coming from the Railway env var, not the toggle — "
                    "flipping this writes a MotherDuck row that overrides it."
                )
            else:
                st.caption(
                    "No stored value and no env var — this is the built-in "
                    "default. A MotherDuck outage looks identical, so treat it "
                    "as 'unconfirmed' rather than 'set'."
                )

            if key == "ac_paused" and st.session_state[skey] is False:
                st.warning(
                    "AC rotation is live: the next run will push new contacts "
                    "into ActiveCampaign and evict stale ones. Current standing "
                    "decision is to leave this paused."
                )

st.divider()

with st.expander("Why isn't Snitcher discovery a button here?"):
    st.write(
        "It runs as a Cowork/Dispatch scheduled task, not a script in the "
        "hub repo — no API to fire a Dispatch task on demand. Status shows "
        "on the Status page (Snitcher Review queue depth) instead."
    )
