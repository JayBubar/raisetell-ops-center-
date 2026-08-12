import requests
import streamlit as st

from config import HUB_BASE_URL, HUB_HEADERS

st.title("📊 Status")
st.caption("Read-only health checks — nothing on this page triggers anything")

# ---------------------------------------------------------------------------
# Service health
# ---------------------------------------------------------------------------
st.subheader("Service Health")

services = {
    "attio-automation-hub": f"{HUB_BASE_URL}/health",
}

cols = st.columns(len(services))
for col, (name, url) in zip(cols, services.items()):
    with col:
        try:
            r = requests.get(url, timeout=10)
            ok = r.status_code == 200
        except requests.exceptions.RequestException:
            ok = False
        st.metric(name, "🟢 Up" if ok else "🔴 Down / Unreachable")

st.divider()

# ---------------------------------------------------------------------------
# AC ↔ Attio bridge
#
# This block used to probe peaceful-generosity-production-312b and print a
# fixed "being rebuilt after the Railway project deletion" note. Both were
# wrong: that host 404s and the bridge never lived there — it's a route inside
# attio-automation-hub. The indicator read Down permanently while the bridge
# was working, so it's now driven by /status/ac-bridge instead.
# ---------------------------------------------------------------------------
st.subheader("AC ↔ Attio Bridge")
st.write(
    "The `Attio Marketing Contact` tag sync. It's the "
    "`/webhooks/activecampaign` route inside attio-automation-hub, not a "
    "separate service — so there's no second host to ping."
)

if st.button("Check AC ↔ Attio bridge"):
    try:
        r = requests.get(
            f"{HUB_BASE_URL}/status/ac-bridge", headers=HUB_HEADERS, timeout=30
        )
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach hub: {e}")
    else:
        c1, c2 = st.columns(2)
        registered = data.get("route_registered")
        c1.metric(
            "Receiver mounted",
            "🟢 Yes" if registered else "🔴 No",
            help=f"POST {data.get('webhook_path')} on {data.get('service')}",
        )

        events = data.get("events") or {}
        if not events.get("available"):
            # Distinct from "no events": the lookup itself failed.
            c2.metric("Last event", "⚠️ Unknown")
            st.warning(
                "Reached the hub, but couldn't read the webhook log — so "
                "traffic can't be confirmed either way. "
                f"{events.get('reason', '')}"
            )
        elif events.get("last_event_at"):
            c2.metric(
                "Last event",
                events["last_event_at"][:19].replace("T", " ") + " UTC",
                help=f"{events.get('events_7d', 0)} in the last 7 days, "
                     f"{events.get('events_total', 0)} all time",
            )
        else:
            c2.metric("Last event", "None yet")
            st.info(
                "The receiver is mounted but has never logged an event. That's "
                "expected if no one has added or removed the tag since webhook "
                "logging was deployed — quiet is not the same as broken."
            )

        if events.get("recent"):
            st.caption("Recent events (ignored ones included — those are the diagnostic):")
            st.dataframe(events["recent"], use_container_width=True)

            ignored = [e for e in events["recent"] if e.get("status") == "ignored"]
            reasons = {e.get("action") for e in ignored}
            if "no_tags_field" in reasons:
                st.warning(
                    "`no_tags_field` events: the AC webhook action isn't sending "
                    "`contact[tags]`, so add vs. remove can't be told apart and "
                    "nothing is written to Attio. Map the tags field in AC."
                )
            if "unexpected_seriesid" in reasons:
                st.warning(
                    "`unexpected_seriesid` events: an automation other than the "
                    "expected one (#"
                    f"{data.get('expected_series_id')}) is posting here."
                )

st.caption(
    "Removing the tag in AC only reaches Attio if automation 15 has a **Tag "
    "Removed** trigger alongside Tag Added. As of 2026-08-12 the AC API "
    "reported only a `tagadd` start — until a `tagremove` trigger is added in "
    "AC's UI, removals send nothing and contacts stay flagged Active in Attio."
)

st.divider()

# ---------------------------------------------------------------------------
# Outlook connection state (Microsoft Graph draft creation)
# ---------------------------------------------------------------------------
st.subheader("Outlook Draft Connection")
st.write(
    "Each rep signs in to Microsoft once so the Task Runner can create "
    "drafts in their own mailbox. Nothing here can send mail."
)
if st.button("Check Outlook connections"):
    try:
        r = requests.get(
            f"{HUB_BASE_URL}/auth/microsoft/status", headers=HUB_HEADERS, timeout=15
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("configured"):
            st.warning(
                "Entra app registration isn't configured on the hub yet — set "
                "AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, HUB_PUBLIC_URL."
            )
        for rep, info in (data.get("reps") or {}).items():
            if info:
                st.success(f"{rep.capitalize()} → {info['upn']}")
            else:
                st.info(f"{rep.capitalize()} — not connected yet")
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach hub: {e}")

st.divider()

# ---------------------------------------------------------------------------
# Smartlead / rotation status (via hub — hub owns the MotherDuck/Attio creds)
# ---------------------------------------------------------------------------
st.subheader("Smartlead Rotation")
st.write(
    "Campaign status and `total_leads` from the Smartlead API, plus the last "
    "`outreach_rotation.py` run from MotherDuck."
)
if st.button("Refresh Smartlead status"):
    try:
        r = requests.get(
            f"{HUB_BASE_URL}/status/smartlead", headers=HUB_HEADERS, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        st.json(data)
        note = (data.get("rotation") or {}).get("note")
        if note:
            st.info(note)
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach hub: {e}")

st.divider()

# ---------------------------------------------------------------------------
# Snitcher Review queue
# ---------------------------------------------------------------------------
st.subheader("Snitcher Review Queue")
st.write(
    "Count of Snitcher Review entries still at Status = New. The list's "
    "parent object is Companies, not People."
)
if st.button("Refresh Snitcher queue"):
    try:
        r = requests.get(
            f"{HUB_BASE_URL}/status/snitcher-review", headers=HUB_HEADERS, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        c1, c2 = st.columns(2)
        c1.metric("Status = New", data["status_new"])
        c2.metric("Total entries", data["total_entries"])
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach hub: {e}")

st.caption(
    "Last discovery-pass timestamp isn't shown: the Snitcher pass runs as a "
    "Cowork/Dispatch task that doesn't log runs anywhere queryable yet."
)

st.divider()

# ---------------------------------------------------------------------------
# Allo tag registry — view, edit later
# ---------------------------------------------------------------------------
st.subheader("Allo Tag Registry")
st.write(
    "`allo_tag_registry` in MotherDuck was built so tag→action mappings "
    "don't require a code deploy to change. This view reads it read-only "
    "for now — inline edit is a natural phase 2 once the read path is "
    "trusted."
)
if st.button("Load tag registry"):
    try:
        r = requests.get(
            f"{HUB_BASE_URL}/status/allo-tag-registry", headers=HUB_HEADERS, timeout=30
        )
        r.raise_for_status()
        rows = r.json()
        if rows:
            st.dataframe(rows, use_container_width=True)
            st.caption(f"{len(rows)} tag mappings · "
                       f"{sum(1 for r_ in rows if r_.get('active'))} active")
        else:
            st.info("Registry is empty.")
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach hub: {e}")

st.caption("`allo_calls` service crash is still open — flagging here until fixed:")
st.warning("allo_calls (Railway) — deferred crash, not yet resolved")
