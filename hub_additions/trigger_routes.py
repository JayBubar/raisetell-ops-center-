"""
MERGED — this file is no longer the source of truth.

The sketch in this file was implemented and now lives in the hub repo at:

    attio-automation-hub/automation_server/ops_center_routes.py

and is registered in automation_server/main.py via
app.include_router(ops_center_router).

Kept as a path placeholder only, so nobody edits a copy that never deploys.
All five TODOs from the sketch are filled in the real file:

  /trigger/outreach-batch     shells out to scripts/outreach.py
  /tasks/{rep}                Attio open tasks ⋈ outreach_email_drafts
  /tasks/{task_id}/complete   PATCH is_completed
  /status/smartlead           Smartlead campaign + total_leads + rotation log
  /status/snitcher-review     list 6d4dce27-180c-42ed-b722-876f51e7c184, Status=New
  /status/allo-tag-registry   MotherDuck allo_tag_registry read

Plus a route the sketch did not have:

  /tasks/{task_id}/draft-email   creates an Outlook draft (see graph_mail.py)
"""
