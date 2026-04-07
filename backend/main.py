import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import PORT, RUN_ON_BOOT, SLACK_CHANNEL_DEVIN_OPS
from db import (
    get_all_issues_ranked, get_issue, get_stats, get_recent_activity,
    get_config, set_config, set_manual_priority, reorder_issues, update_dispatch, log_activity,
    get_completed_this_week, get_needs_human_issues,
)
from triage import fetch_and_triage_new_issues
from dispatcher import dispatch_issue_by_number, dispatch_next_in_queue
from poller import poll_active_devin_sessions
from board import sync_github_project_board
from slack_client import send_morning_digest, handle_slack_command

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Cron jobs ----
    scheduler.add_job(fetch_and_triage_new_issues, "interval", minutes=5, id="triage")
    scheduler.add_job(poll_active_devin_sessions, "interval", minutes=1, id="poller")
    scheduler.add_job(sync_github_project_board, "interval", minutes=5, id="board")

    # Notion stats sync every 5 min
    async def _notion_stats():
        try:
            from notion_client_mod import sync_notion_stats
            await sync_notion_stats(get_stats())
        except Exception as e:
            print(f"[cron] Notion stats sync failed: {e}")
    scheduler.add_job(_notion_stats, "interval", minutes=5, id="notion_stats")

    # Morning digest + weekly Notion digest on weekdays at 9am, Mondays also get weekly digest
    async def _morning():
        await send_morning_digest()
        if datetime.now().weekday() == 0:  # Monday
            try:
                from notion_client_mod import create_weekly_digest
                stats = get_stats()
                completed = get_completed_this_week()
                needs_human = get_needs_human_issues()
                await create_weekly_digest(stats, completed, needs_human)
            except Exception as e:
                print(f"[cron] Notion weekly digest failed: {e}")
    scheduler.add_job(_morning, "cron", hour=9, minute=0, day_of_week="mon-fri", id="morning")

    # Autopilot dispatch every 5 min
    async def _autopilot():
        if get_config("mode") == "autopilot":
            await dispatch_next_in_queue()
    scheduler.add_job(_autopilot, "interval", minutes=5, id="autopilot")

    scheduler.start()
    print(f"[backend] Devin Autopilot backend running on :{PORT}")
    print(f"[backend] Mode: {get_config('mode')}")

    if RUN_ON_BOOT:
        asyncio.create_task(fetch_and_triage_new_issues())

    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---- API endpoints ----

@app.get("/api/issues")
def api_issues():
    return get_all_issues_ranked()

@app.post("/api/issues/reorder")
async def api_reorder(request: Request):
    body = await request.json()
    ordered = body.get("order", [])
    if not ordered:
        return JSONResponse({"error": "order required"}, 400)
    reorder_issues(ordered, "dashboard")
    log_activity(None, "reorder", f"Queue manually reordered ({len(ordered)} issues)", "dashboard")
    return {"ok": True}

@app.get("/api/issues/{number}")
def api_issue_detail(number: int):
    issue = get_issue(number)
    if not issue:
        return JSONResponse({"error": "not found"}, 404)
    activity = [a for a in get_recent_activity(100) if a.get("github_number") == number]
    return {**issue, "activity": activity}

@app.get("/api/stats")
def api_stats(period: str = "7d"):
    return get_stats(period)

@app.get("/api/activity")
def api_activity():
    return get_recent_activity(50)

@app.post("/api/issues/{number}/dispatch")
async def api_dispatch(number: int, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        await dispatch_issue_by_number(
            number,
            body.get("triggered_by", "dashboard"),
            human_instructions=body.get("human_instructions"),
        )
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@app.post("/api/issues/{number}/pause")
def api_pause(number: int):
    update_dispatch(number, {"dispatch_status": "paused"})
    log_activity(number, "paused", f"Issue #{number} paused", "dashboard")
    return {"ok": True}

@app.post("/api/issues/{number}/prioritize")
async def api_prioritize(number: int, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    user = body.get("user", "dashboard")
    set_manual_priority(number, user)
    log_activity(number, "prioritized", f"{user} moved issue #{number} to top of queue", "dashboard")
    return {"ok": True}

@app.post("/api/config/mode")
async def api_set_mode(request: Request):
    body = await request.json()
    mode = body.get("mode")
    if mode not in ("supervised", "autopilot"):
        return JSONResponse({"error": "invalid mode"}, 400)
    set_config("mode", mode)
    log_activity(None, "mode_change", f"Mode set to {mode}", "dashboard")
    return {"ok": True, "mode": mode}

@app.get("/api/config")
def api_config():
    return {
        "mode": get_config("mode"),
        "autopilot_max_concurrent": get_config("autopilot_max_concurrent"),
    }

@app.post("/api/slack/commands")
async def api_slack_commands(request: Request):
    form = await request.form()
    command = form.get("command", "")
    text = form.get("text", "")
    user_name = form.get("user_name", "")
    channel_id = form.get("channel_id", "")
    msg = await handle_slack_command(command, text, user_name, channel_id)
    return {"response_type": "ephemeral", "text": msg}

@app.post("/api/notion/init")
async def api_notion_init(request: Request):
    try:
        body = await request.json()
        page_id = body.get("pageId")
        if not page_id:
            return JSONResponse({"error": "pageId required"}, 400)
        from notion_client_mod import init_notion_database
        db_id = await init_notion_database(page_id)
        set_config("notion_database_id", db_id)
        return {"ok": True, "database_id": db_id}
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)

@app.post("/api/slack/status")
async def api_slack_status(request: Request):
    """Post a status report to #devin-ops. Can also be triggered from dashboard."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    period = body.get("period", "7d")
    from slack_client import handle_slack_command
    await handle_slack_command("/devin", f"status {period}", "dashboard", SLACK_CHANNEL_DEVIN_OPS)
    return {"ok": True}

@app.post("/api/poll")
async def api_poll():
    await poll_active_devin_sessions()
    return {"ok": True}

@app.post("/api/triage")
async def api_triage():
    await fetch_and_triage_new_issues()
    return {"ok": True}

@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
