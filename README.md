# RaiseTell Ops Center

A Streamlit trigger panel + status board. Second service in the same Railway
project as `attio-automation-hub`, not a new hosting platform.

## Structure

```
app.py                    # entry point, nav
config.py                 # HUB_BASE_URL, shared auth token, timeouts
pages/
  1_Triggers.py           # buttons -> POST hub routes
  2_Status.py             # health checks, read-only
  3_Tasks.py              # Attio task runner + Outlook drafts
  4_Tracker.py            # campaign engagement history (placeholder, see below)
hub_additions/            # pointers only -- the live code is in the hub repo
requirements.txt
railway.json
```

## Why this shape

- The Streamlit app never touches Attio/MotherDuck/Smartlead credentials
  directly — it calls routes on `attio-automation-hub`, which already has
  the auth wired. One place for secrets, not two.
- Buttons call hub routes over HTTPS, not local subprocess calls from
  Streamlit itself — same pattern whether you're looking at this from your
  desktop or your phone.
- A shared `OPS_CENTER_TOKEN` header gates every trigger route so it's not
  a public "run arbitrary script" endpoint sitting on the internet.

## What's live

- **Trigger:** uncontacted outreach batch per rep, with a dry-run option
- **Automation flags:** pause/resume the AC rotation from the Triggers page.
  Writes through the hub's `/config/flags` into MotherDuck, which
  `outreach_rotation.py` reads at the start of each run — so resuming is a
  toggle, not an edit and a redeploy. A rejected write snaps the switch back
  rather than showing a state the scheduled job won't obey, and a flag with
  no stored value is labelled unconfirmed (a MotherDuck outage looks
  identical to "never set")
- **Status:** hub health, AC↔Attio bridge, Smartlead rotation
  summary, Snitcher Review queue depth, Allo tag registry, Outlook
  connection state per rep.
  The bridge panel reads the hub's `/status/ac-bridge` rather than pinging a
  second host — the bridge is a route *inside* attio-automation-hub, and the
  old tile probed `peaceful-generosity-…`, a URL it never ran on, so it showed
  Down permanently while working. It now reports whether the receiver is
  mounted and when it last actually received an event, kept separate on
  purpose: quiet is not broken, and an unreadable log is not "no traffic"
- **Tasks:** open Attio tasks with their AI-drafted email inline; complete a
  task, or push the draft into the rep's own Outlook Drafts folder
- **Campaigns:** pick a campaign, get its target list, funnel (targeted →
  attended → meeting scheduled → follow-up breakdown), cross-channel activity
  feed, and Won value vs. Budget.
  All of it comes from the hub's `/campaigns` routes rather than being
  assembled here — this service has no `MOTHERDUCK_TOKEN`, and resolving list
  membership once server-side means the funnel, the feed, and the deal roll-up
  all describe the same set of people instead of catching the list mid-edit.
  The deal-value basis is selectable because the plain *Deal value* field is
  empty workspace-wide; ARR + Implementation is the default
- **Flagged, not actioned:** `allo_calls` crash, Cal.com reconciliation
  (placeholder button, disabled until that script exists)

## Tracker — structure only, on purpose

`4_Tracker.py` has the campaign selector, summary tiles, and the shape of
the eventual detail view, but reads nothing. Its data source
(`hubspot_email_archive.main.contact_activity_log`) exists and is empty; the
hub's `/webhooks/ac-form-fill` route fills it once the five AC automations
have their Webhook blocks pointed at it.

Wiring the tiles needs a read route on the hub — there isn't one yet, and
deliberately so: it's worth seeing the real row shape before designing a
query around it. Social Media and Conference follow-ups stay empty until
those sources exist. They land in the same table under a different `source`,
so nothing here gets redesigned when they do.

## Deliberately out of scope

- Attio-native workflows/sequences — no API to trigger these, status only,
  tracked separately
- Snitcher discovery — runs as a Cowork/Dispatch task, not callable from
  here; status page shows queue depth but can't fire the pass itself
- ActiveCampaign automations — event-triggered natively, nothing to click
- **Sending** email. Drafts only, always. The rep presses Send in Outlook.

## Two timeouts that have to stay in order

`config.TRIGGER_TIMEOUT` (660s) must stay **above** the hub's
`OUTREACH_TIMEOUT_SECONDS` (600s). If this side gives up first, the batch
keeps running and mutating Attio with nobody reading the result — you'd see
a failure message for a run that half-succeeded. Change one, change both.

## Environment variables

| Variable | Notes |
| --- | --- |
| `HUB_BASE_URL` | Defaults to the hub's Railway domain. |
| `OPS_CENTER_TOKEN` | Must be the **same value** as on the hub service. |

## Deploying

Second service in the Railway `Smartlead` project, Root Directory pointed at
this folder. Railpack didn't auto-detect the hub until Root Directory was set
explicitly — expect the same here. `railway.json` already carries the
Streamlit start command.

## Test order

1. Dry-run the outreach batch trigger (batch size 1–2).
2. Confirm `outreach_batch_checkpoint` is actually being written in
   MotherDuck.
3. Real batch of 1–2 contacts. Check the Attio tasks and the
   `outreach_email_drafts` rows.
4. Only then trust it at batch size 25.
5. Task Runner and the Outlook draft action after the trigger path is solid —
   the draft action additionally needs the Entra app registration and each
   rep's one-time sign-in.

## Next build passes

- Tracker: hub read route over `contact_activity_log`, then wire the tiles
  and add the contact-list/timeline detail view
- Write Task Runner subject/body edits back to `outreach_email_drafts`
- Click-tracking redirect route + dashboard tile, once that service exists
- Allo tag registry inline edit (currently read-only)
- `outreach_rotation.py` doesn't write `outreach_rotation_log` yet, so
  "last rotation run" on the Status page has no source
