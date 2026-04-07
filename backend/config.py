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
