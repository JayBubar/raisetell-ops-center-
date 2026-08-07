"""
APPLIED — this patch has been merged into the script it targeted.

The CSV checkpoint in outreach.py was replaced with the MotherDuck version.
The live code is at:

    attio-automation-hub/automation_server/scripts/outreach.py

What was applied, beyond the literal patch in the original sketch:

  - load_checkpoint() / append_checkpoint() now read and write
    hubspot_email_archive.main.outreach_batch_checkpoint
  - main() opens ONE MotherDuck connection up top and passes it to the
    checkpoint and draft writes, as the patch notes suggested
  - append_checkpoint() is called once PER CONTACT inside the batch loop,
    not once with the whole list at the end. The original code only wrote
    the checkpoint after the loop finished, so a crash or timeout at
    contact 12 of 25 left 12 people with live Attio tasks and no checkpoint
    row — the next run would re-select and re-email them. Moving the
    checkpoint to MotherDuck alone would not have fixed that.

Kept as a path placeholder only, so nobody edits a copy that never deploys.
"""
