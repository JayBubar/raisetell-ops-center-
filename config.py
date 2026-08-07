"""
Shared config for Ops Center pages.

HUB_BASE_URL points at the existing attio-automation-hub FastAPI service.
Set as a Railway environment variable on the Streamlit service so the same
code works locally (.env) and deployed.
"""

import os

HUB_BASE_URL = os.environ.get(
    "HUB_BASE_URL",
    "https://attio-automation-hub-production.up.railway.app",
)

# Shared secret the Streamlit app sends as a header on every trigger call.
# The hub checks this before running anything — keeps the trigger routes from
# being callable by anyone who guesses the URL. Set OPS_CENTER_TOKEN on both
# the Streamlit service and the hub service in Railway Variables.
OPS_CENTER_TOKEN = os.environ.get("OPS_CENTER_TOKEN", "")

HUB_HEADERS = {"Authorization": f"Bearer {OPS_CENTER_TOKEN}"}

# The hub kills the outreach subprocess at 600s. This must stay above that,
# or Streamlit abandons the request while the batch is still creating Attio
# tasks -- you would see a failure for a run that actually half-succeeded.
TRIGGER_TIMEOUT = 660

REPS = ["kurt", "jay", "joel"]
