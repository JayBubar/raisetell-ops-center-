"""
RaiseTell Ops Center — main entry point.

Run locally:   streamlit run app.py
Deploy:        second service in the same Railway project as attio-automation-hub
               (see railway.json). Streamlit auto-discovers pages/ for the sidebar nav.
"""

import streamlit as st

st.set_page_config(
    page_title="RaiseTell Ops Center",
    page_icon="🦓",
    layout="wide",
)

st.title("🦓 RaiseTell Ops Center")
st.caption("Trigger panel + status board for the automation stack")

st.markdown(
    """
    Use the sidebar to navigate:

    - **Triggers** — one-click runs for scripts that currently require you at a keyboard
    - **Status** — health of the webhook receivers, Smartlead, Allo tag registry
    - **Tasks** — Attio task list/complete view (build phase 2)
    - **Tracker** — campaign engagement history; structure only until
      `contact_activity_log` has rows in it
    - **Campaigns** — per-campaign funnel, activity, and Won value vs. Budget,
      resolved through the campaign's Target List Slug

    This app does not run scripts itself — it calls routes on the
    `attio-automation-hub` FastAPI service (same Railway project), which owns
    the actual Attio/MotherDuck/Smartlead credentials. Keeps secrets in one
    place and this UI disposable/rebuildable.
    """
)
