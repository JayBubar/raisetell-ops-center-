import streamlit as st

st.title("📈 Campaign Tracker")
st.caption(
    "Engagement history across sources — AC form fills today, Social and "
    "Conference follow-ups later. Placeholder structure now, real data and "
    "detail views come once the underlying pipelines exist."
)

# ---------------------------------------------------------------------------
# Campaign selector — supports multiple campaigns from day one, even though
# only one source (AC forms) feeds it right now.
# ---------------------------------------------------------------------------
CAMPAIGNS = [
    "All campaigns",
    "AC Form Fills",       # live once the one-way sync ships
    "Social Media",        # not built yet
    "Conference Follow-ups",  # not built yet
]

campaign = st.selectbox("Campaign", CAMPAIGNS)

st.divider()

if campaign == "All campaigns":
    st.info(
        "Once wired up, this reads from MotherDuck's contact_activity_log "
        "table, grouped by source. Each campaign below becomes its own "
        "filtered view of the same table."
    )
else:
    st.info(f"'{campaign}' has no data source connected yet.")

st.write("")

# ---------------------------------------------------------------------------
# Placeholder summary tiles — shape only, not wired to real counts yet.
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total tracked events", "—")
with col2:
    st.metric("Unique contacts", "—")
with col3:
    st.metric("Sources live", "0 of 4")

st.divider()

with st.expander("What this becomes"):
    st.write(
        "- **Data source:** MotherDuck `contact_activity_log` "
        "(source, event_type, contact_email, timestamp, details)\n"
        "- **First source to land:** AC form fills — one-way sync, no "
        "workflows triggered, just logs the event and updates the "
        "'Filled Form' field on the Attio person record\n"
        "- **Future sources:** Social Media, Conference follow-ups, "
        "Deals activity — same table, same shape, new `source` values\n"
        "- **Detail view (not built):** click into a campaign to see the "
        "actual contact list and event timeline, filterable by date range"
    )
