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
    "AC ↔ Attio bridge (peaceful-generosity)": (
        "https://peaceful-generosity-production-312b.up.railway.app/health"
    ),
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

st.caption(
    "AC ↔ Attio bridge is currently being rebuilt after the Railway project "
    "deletion — expect Down here until that's redeployed."
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
