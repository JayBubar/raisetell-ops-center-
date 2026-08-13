"""
Campaign Detail — activity, funnel, and ROI for one campaign's target list.

Everything comes from the hub's /campaigns routes rather than being assembled
here: the hub holds the Attio and MotherDuck credentials (this service has no
MOTHERDUCK_TOKEN at all), and resolving list membership once server-side means
the funnel, the activity feed, and the deal roll-up are all describing the same
set of people. Four separate calls could each catch the list mid-edit and
quietly disagree.
"""

import requests
import streamlit as st

from config import HUB_BASE_URL, HUB_HEADERS

st.title("🎯 Campaign Detail")
st.caption("Read-only. Nothing on this page writes to Attio or MotherDuck.")

VALUE_BASES = {
    "arr_plus_implementation": "ARR + Implementation",
    "arr_only": "ARR only",
    "deal_value_field": "Deal value field",
}


def hub_get(route: str, params: dict | None = None, timeout: int = 120):
    try:
        r = requests.get(f"{HUB_BASE_URL}{route}", headers=HUB_HEADERS,
                         params=params or {}, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.RequestException as e:
        return None, str(e)


def money(v):
    return "—" if v is None else f"${v:,.0f}"


campaigns, err = hub_get("/campaigns", timeout=30)
if err:
    st.error(f"Could not reach the hub: {err}")
    st.stop()
if not campaigns:
    st.info("No campaigns in Attio yet. Create one on the Campaigns object.")
    st.stop()

c1, c2 = st.columns([3, 2])
with c1:
    choice = st.selectbox(
        "Campaign", campaigns,
        format_func=lambda c: f"{c['name']} · {c['status'] or 'No status'}",
    )
with c2:
    basis = st.selectbox(
        "Deal value basis", list(VALUE_BASES),
        format_func=lambda b: VALUE_BASES[b],
        help="Which currency field(s) on Deals count toward Won value.",
    )

if not choice.get("target_list_slug"):
    st.warning(
        f"**{choice['name']}** has no Target List Slug, so it has no targets. "
        "Set that field on the Campaign record in Attio to the list's api_slug."
    )

if not st.button("Load campaign", type="primary"):
    st.stop()

with st.spinner("Resolving list membership, activity, and deals…"):
    data, err = hub_get(f"/campaigns/{choice['record_id']}/detail", {"basis": basis})
if err:
    st.error(f"Could not load campaign: {err}")
    st.stop()

camp = data["campaign"]
targets = data["targets"]
funnel = data["funnel"]
activity = data["activity"]
deals = data["deals"]
roi = data["roi"]

st.header(camp["name"] or "Untitled campaign")
meta = " · ".join(x for x in [
    camp["status"],
    ", ".join(camp["type"] or []) or None,
    camp["event_name_details"],
    f"{camp['start_date'] or '?'} → {camp['end_date'] or '?'}",
] if x)
st.caption(meta)

# ---------------------------------------------------------------------------
# ROI
# ---------------------------------------------------------------------------
st.subheader("Return")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Budget", money(roi["budget"]))
m2.metric("Won value", money(roi["won_value"]),
          help=f"{deals['won_count']} won of {deals['count']} linked deals, "
               f"on {VALUE_BASES[basis]}")
m3.metric("Net", money(roi["net"]))
m4.metric("ROI", "—" if roi["roi_pct"] is None else f"{roi['roi_pct']:.0f}%")

if deals["count"] == 0:
    st.info(
        "No deals are linked to this campaign yet, so Won value is $0 by "
        "absence rather than by outcome. Link deals via the **Campaign** field "
        "on the Deal record in Attio."
    )
elif deals["basis_all_empty"]:
    # The failure this page most needs to not have: a confident $0.
    st.warning(
        f"Every linked deal has **{VALUE_BASES[basis]}** empty, so this total "
        "is 0 because the field is unset — not because the deals are worthless. "
        "As of 2026-08-13 the plain *Deal value* field is unpopulated across "
        "the whole workspace; ARR + Implementation is the basis with real "
        "numbers behind it."
    )

if deals["deals"]:
    st.caption(f"Linked deals · basis fields: `{'` + `'.join(deals['basis_fields'])}`")
    st.dataframe(
        [{
            "Deal": d["name"],
            "Stage": d["stage"],
            "Counts toward Won": "✅" if d["is_won"] else "",
            VALUE_BASES[basis]: d["basis_value"],
            "ARR": d["amounts"]["deal_value_arr"],
            "Implementation": d["amounts"]["deal_value_implementation"],
            "Deal value": d["amounts"]["value"],
        } for d in deals["deals"]],
        use_container_width=True, hide_index=True,
    )
    if deals["open_value"]:
        st.caption(f"Open (not yet Won) on this basis: {money(deals['open_value'])}")

st.divider()

# ---------------------------------------------------------------------------
# Funnel
# ---------------------------------------------------------------------------
st.subheader("Funnel")

if targets["error"]:
    st.error(targets["error"])
else:
    f1, f2, f3 = st.columns(3)
    targeted = funnel["targeted"]
    f1.metric("Targeted", targeted)
    f2.metric("Attended", funnel["attended"],
              help=f"{funnel['attended'] / targeted * 100:.0f}% of targets"
              if targeted else None)
    f3.metric("Meeting scheduled", funnel["meeting_scheduled"],
              help=f"{funnel['meeting_scheduled'] / targeted * 100:.0f}% of targets"
              if targeted else None)

    b1, b2 = st.columns(2)
    with b1:
        st.caption("Follow-up status")
        st.dataframe(
            [{"Status": k, "People": v} for k, v in sorted(funnel["follow_up_status"].items())],
            use_container_width=True, hide_index=True,
        )
    with b2:
        st.caption("Source")
        st.dataframe(
            [{"Source": k, "People": v} for k, v in sorted(funnel["source"].items())],
            use_container_width=True, hide_index=True,
        )

    with st.expander(f"Target list — {targets['count']} people (`{targets['list_slug']}`)"):
        st.caption(
            "Live list membership, read at load time. Someone added or removed "
            "in Attio since then won't appear until you reload."
        )
        st.dataframe(
            [{
                "Name": m["name"], "Email": m["email"],
                "Attended": "✅" if m["attended_event"] else "",
                "Meeting": "✅" if m["in_person_meeting_scheduled"] else "",
                "Follow-up": m["follow_up_status"],
                "Source": ", ".join(m["source"] or []),
                "Notes": m["notes"],
            } for m in targets["members"]],
            use_container_width=True, hide_index=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------
st.subheader("Activity")
st.caption(
    "`contact_activity_log` rows for this campaign's targets, joined on email "
    "at query time. The log has no campaign column on purpose — a contact can "
    "be on several campaign lists at once, so attributing a row to one "
    "campaign when it's written would be guessing."
)

if not activity["available"]:
    # Not the same as an empty feed, and must not render as one.
    st.error(
        "Could not read the activity log, so this is 'unknown', not 'nothing "
        f"happened'. {activity.get('reason', '')}"
    )
elif activity["rows"]:
    st.caption(
        f"{len(activity['rows'])} events across {activity['matched_emails']} "
        f"of {activity.get('queried_emails', 0)} targeted contacts"
    )
    st.dataframe(activity["rows"], use_container_width=True, hide_index=True)
else:
    st.info(
        "No activity recorded for these contacts. `contact_activity_log` is "
        "currently empty workspace-wide: only the AC form-fill route writes to "
        "it, and AC marketing emails, Allo calls, and landing-page/social "
        "events are not wired up yet. This panel fills in as those land."
    )
    if activity.get("note"):
        st.caption(activity["note"])
