# Devin Autopilot

AI-powered GitHub issue triage and autonomous resolution system using the Devin API. Built for FinServ Co — an enterprise engineering team drowning in 300+ stale GitHub issues.

## What this does

A system that ingests GitHub issues, uses Devin to batch-triage them (scoring fixability, impact, complexity, risk), ranks them by priority, and dispatches auto-fixable ones to Devin for autonomous code fixes. Engineers stay in the loop via a real-time dashboard, Slack notifications, and GitHub comments — without babysitting the process.

## How it works

1. **Ingest** — Polls GitHub for open issues every 5 minutes
2. **Triage** — Sends all untriaged issues to Devin in a single batch session. Devin analyzes each issue and returns fixability, impact, complexity scores, affected files, and whether it can be auto-fixed
3. **Prioritize** — Ranks issues using: `fixability×0.4 + impact×0.3 + staleness×0.2 + (10-complexity)×0.1`. Engineers can override by dragging rows or using `/devin prioritize`
4. **Dispatch** — One-click dispatch from dashboard, Slack command, or autopilot mode. Devin clones the repo, reads the code, makes the fix, runs tests, and opens a PR
5. **Track** — Poller monitors Devin sessions, detects PRs, tracks merges. Updates flow to dashboard, Slack, GitHub comments, and Notion

## Setup

### 1. Create the target repo

Create a GitHub repo (or fork an existing monorepo) and enable Issues.

### 2. Install dependencies

```bash
# Backend (Python)
cd backend && pip install -r requirements.txt

# Dashboard (Next.js)
cd dashboard && npm install
```

### 3. Configure environment

```bash
cp .env.example backend/.env
```

Required variables:
- `GITHUB_TOKEN` — GitHub personal access token (needs repo scope)
- `GITHUB_OWNER` — Your GitHub username or org
- `GITHUB_REPO` — Target repo name
- `DEVIN_API_KEY` — Devin API key (from app.devin.ai)

Optional variables:
- `GITHUB_PROJECT_ID` — GitHub Projects v2 board ID (for project board sync)
- `SLACK_BOT_TOKEN` — Slack bot OAuth token (for Slack integration)
- `SLACK_SIGNING_SECRET` — Slack app signing secret (for slash command verification)
- `SLACK_CHANNEL_DEVIN_OPS` — Slack channel for ops commands (default: `#devin-ops`)
- `SLACK_CHANNEL_ENG_ALERTS` — Slack channel for notifications (default: `#eng-alerts`)
- `NOTION_API_KEY` — Notion integration token (for Notion database sync)
- `NOTION_DATABASE_ID` — Notion database ID (for issue tracking board)
- `DASHBOARD_URL` — Dashboard URL for links in Slack messages (default: `http://localhost:3000`)
- `BACKEND_URL` — Backend URL (default: `http://localhost:4000`)
- `PORT` — Backend server port (default: `4000`)
- `RUN_ON_BOOT` — Set to `1` to run fetch+triage immediately on backend start (useful for demos)

### 4. Run

```bash
# Terminal 1 — backend
cd backend && RUN_ON_BOOT=1 python3 main.py

# Terminal 2 — dashboard
cd dashboard && npm run dev
```

Open `http://localhost:3000`.

## Architecture

```
GitHub repo (issues)
    ↓ poll every 5 min
Backend (FastAPI + SQLite + APScheduler)
    ↓ batch triage via Devin API
    ↓ comment + label on GitHub
    ↓ dispatch → Devin API (creates session)
    ↓ poll session → detect PR → track merge
Dashboard (Next.js)
    ↔ reads/writes via backend API
Slack
    ← notifications (dispatch, PR ready, stuck)
    → slash commands (/devin status, dispatch, prioritize)
Notion (optional)
    ← database sync, weekly digest, stats
```

## File layout

```
devin-autopilot/
├── backend/              FastAPI + SQLite + APScheduler
│   ├── main.py           API endpoints + cron jobs
│   ├── db.py             SQLite schema + CRUD
│   ├── triage.py         Batch Devin triage
│   ├── dispatcher.py     Devin session creation + prompt building
│   ├── poller.py         Session status + PR merge tracking
│   ├── github_client.py  GitHub API (issues, comments, labels, PRs)
│   ├── slack_client.py   Slack notifications + slash commands
│   ├── notion_client_mod.py  Notion database sync
│   ├── board.py          GitHub Projects v2 board sync
│   ├── templates.py      GitHub comment + Slack message templates
│   └── config.py         Environment variable loading
├── dashboard/            Next.js App Router
│   ├── app/              Pages + API proxy routes
│   └── components/       UI components
├── .env.example          Environment variable template
└── README.md
```

## Operating modes

- **Supervised** (default): Devin triages and scores everything, but waits for a human to dispatch via the dashboard, GitHub label, or `/devin dispatch #N` in Slack.
- **Autopilot**: Automatically dispatches the top N queued auto-fixable issues every 5 minutes. Concurrency controlled by `autopilot_max_concurrent`.

Toggle at the top of the dashboard or via `/devin autopilot on|off`.

## Slack commands

- `/devin status` — executive status report with metrics, in-progress items, PRs awaiting review
- `/devin status 24h|7d|30d` — status filtered by time period
- `/devin dispatch #N` — dispatch an issue to Devin
- `/devin prioritize #N` — move issue to top of queue
- `/devin stop #N` — pause an active Devin session
- `/devin autopilot on|off` — toggle operating mode

## Dashboard features

- **Stats row** — 6 metric cards (open issues, Devin ready, in progress, PRs open, dispatched, closed) with time period filter (24h, 7d, 30d, all time)
- **Drag-to-reorder** issue queue with persistent manual priority override
- **Status filter tabs** — filter queue by All, Queued, In Progress, PR Open, Done, Failed
- **Issue drawer** — full triage detail with fixability/impact/complexity scores, affected files, risk level, AI-generated instructions, and session log timeline
- **Session log timeline** — visual timeline with emoji icons, timestamps, and color-coded events tracking the full lifecycle (triaged → dispatched → PR opened → merged)
- **Human instructions input** — optional for auto-fixable issues, required for needs-human issues before dispatch
- **One-click dispatch** — dispatch from the queue row or from within the drawer
- **Real-time status tracking** — automatic 10s polling when issues are in-progress, 30s otherwise (queued → in progress → PR open → done)
- **Mode toggle** — switch between Supervised and Autopilot from the top bar
- **Direct links** — "View in Devin" and "View Pull Request" buttons in the drawer

## Why Devin

Unlike other coding agents, Devin runs full autonomous sessions — it clones the repo, reads and understands context across files, makes targeted fixes, runs tests, and opens PRs. This system uses Devin for both the intelligence layer (triage/analysis) and the execution layer (code fixes), creating an end-to-end pipeline from issue to merged PR.
