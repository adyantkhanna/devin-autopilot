# Devin Autopilot

AI-powered GitHub issue triage + autonomous dispatch to Devin. Built for a demo to a VP of Engineering at FinServ Co.

## What this is

A backend that polls GitHub, triages issues with Claude, dispatches auto-fixable ones to Devin, posts progress to GitHub + Slack, and surfaces everything through a Next.js dashboard.

## Setup

### 1. Fork the target repo

Fork `https://github.com/vercel/turborepo` into your GitHub account and rename it to `finserv-monorepo` (public).

### 2. Install dependencies

```bash
cd backend && npm install
cd ../dashboard && npm install
```

### 3. Configure environment

```bash
cp .env.example backend/.env
# Fill in GITHUB_TOKEN, ANTHROPIC_API_KEY, DEVIN_API_KEY, SLACK_*
```

The dashboard reads `BACKEND_URL` (defaults to `http://localhost:4000`).

### 4. Seed issues + labels

```bash
GITHUB_TOKEN=xxx GITHUB_OWNER=your-username node seed-issues.js
```

This creates the 12 demo issues and all required labels.

### 5. (Optional) Create the Project board

Create a GitHub Project v2 named "Devin Autopilot" with a **Status** single-select field containing these options: `Untriaged`, `Devin Ready`, `Needs Human`, `In Progress`, `PR Open`, `Closed`. Then set `GITHUB_PROJECT_ID` in `.env` to the project's node ID.

### 6. Run

```bash
# Terminal 1 — backend
cd backend && RUN_ON_BOOT=1 npm start

# Terminal 2 — dashboard
cd dashboard && npm run dev
```

Open `http://localhost:3000`.

## Architecture

```
GitHub repo (issues)
    ↓ poll every 5 min
Backend (Express + SQLite)
    ↓ LLM triage (Claude Opus)
    ↓ comment + label + board move
    ↓ dispatch → Devin API
    ↓ poll session → PR comment + Slack
Dashboard (Next.js)
    ↔ reads/writes via backend API
Slack
    ← notifications
    → slash commands → backend
```

## File layout

```
devin-autopilot/
├── backend/        Express + SQLite + cron
│   ├── index.js
│   ├── db.js
│   ├── github.js
│   ├── triage.js
│   ├── dispatcher.js
│   ├── poller.js
│   ├── slack.js
│   ├── board.js
│   └── templates.js
├── dashboard/      Next.js App Router
│   ├── app/
│   └── components/
├── seed-issues.js
├── .env.example
└── README.md
```

## Operating modes

- **Supervised** (default): Triages and scores everything but waits for a human to dispatch via dashboard button, `dispatch-devin` label, or `/devin dispatch #N` in Slack.
- **Autopilot**: Cron job dispatches the top N `devin-ready` issues automatically every 5 min. Concurrency limit: `autopilot_max_concurrent` in `system_config`.

Toggle at the top of the dashboard or via `/devin autopilot on|off`.

## Slack commands

- `/devin status` — snapshot of queue
- `/devin prioritize #N` — move issue to top
- `/devin dispatch #N` — dispatch immediately
- `/devin stop #N` — pause active session
- `/devin autopilot on|off` — flip mode

Point your Slack app's slash commands at `POST /api/slack/commands`.

## Prioritization

```
priority_score = fixability*0.4 + impact*0.3 + staleness*0.2 + complexity_inverse*0.1
```

Manual overrides (drag on dashboard, `/devin prioritize`) always beat the LLM score and are stored with user + timestamp.
