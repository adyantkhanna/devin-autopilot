import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "finserv-monorepo")
GITHUB_PROJECT_ID = os.getenv("GITHUB_PROJECT_ID", "")

DEVIN_API_KEY = os.getenv("DEVIN_API_KEY", "")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_CHANNEL_DEVIN_OPS = os.getenv("SLACK_CHANNEL_DEVIN_OPS", "#devin-ops")
SLACK_CHANNEL_ENG_ALERTS = os.getenv("SLACK_CHANNEL_ENG_ALERTS", "#eng-alerts")

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000")
PORT = int(os.getenv("PORT", "4000"))
RUN_ON_BOOT = os.getenv("RUN_ON_BOOT", "0") == "1"

# Polling & scheduling intervals
TRIAGE_INTERVAL_MINUTES = 5
POLLER_INTERVAL_MINUTES = 1
AUTOPILOT_INTERVAL_MINUTES = 5

# Devin session defaults
DEVIN_POLL_INTERVAL_SECONDS = 2
DEVIN_TRIAGE_TIMEOUT_SECONDS = 900
DEVIN_DISPATCH_TIMEOUT_SECONDS = 30

# Dashboard
AUTO_REFRESH_SECONDS = 30

# Estimated hours saved per resolved issue (for metrics)
HOURS_SAVED_PER_ISSUE = 3
