import json
from datetime import datetime
from dateutil.parser import parse as parse_date
from notion_client import Client

from config import NOTION_API_KEY, NOTION_DATABASE_ID, GITHUB_OWNER, GITHUB_REPO

notion = Client(auth=NOTION_API_KEY) if NOTION_API_KEY else None


def _get_db_id():
    return NOTION_DATABASE_ID


# ---- initNotionDatabase ----

async def init_notion_database(parent_page_id: str) -> str:
    resp = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Devin Autopilot — Backlog Command Center"}}],
        properties={
            "Title": {"title": {}},
            "Issue #": {"number": {}},
            "Priority Rank": {"number": {}},
            "Priority Score": {"number": {"format": "number"}},
            "Fixability": {"number": {"format": "number"}},
            "Impact": {"number": {"format": "number"}},
            "Complexity": {"select": {"options": [
                {"name": "Low", "color": "green"},
                {"name": "Medium", "color": "yellow"},
                {"name": "High", "color": "red"},
            ]}},
            "Auto-fixable": {"select": {"options": [
                {"name": "Yes", "color": "green"},
                {"name": "Maybe", "color": "yellow"},
                {"name": "No", "color": "red"},
            ]}},
            "Risk": {"select": {"options": [
                {"name": "Low", "color": "green"},
                {"name": "Medium", "color": "yellow"},
                {"name": "High", "color": "red"},
            ]}},
            "Status": {"select": {"options": [
                {"name": "Untriaged", "color": "default"},
                {"name": "Devin Ready", "color": "green"},
                {"name": "In Progress", "color": "yellow"},
                {"name": "PR Open", "color": "blue"},
                {"name": "Closed", "color": "purple"},
                {"name": "Needs Human", "color": "red"},
            ]}},
            "Triage Summary": {"rich_text": {}},
            "Affected Files": {"rich_text": {}},
            "Days Open": {"number": {}},
            "PR Link": {"url": {}},
            "GitHub Link": {"url": {}},
            "Dispatched At": {"date": {}},
            "Completed At": {"date": {}},
        },
    )
    db_id = resp["id"]
    try:
        notion.blocks.children.append(
            block_id=parent_page_id,
            children=[_callout_block("📊 Stats update automatically as Devin triages and fixes issues."), _divider_block()],
        )
    except Exception as e:
        print(f"[notion] Could not add intro blocks: {e}")
    print(f"[notion] Database created: {db_id}")
    return db_id


# ---- helpers ----

def _complexity_label(score):
    if score is None:
        return None
    if score <= 3:
        return "Low"
    if score <= 6:
        return "Medium"
    return "High"

def _auto_fixable_label(auto_fixable, fixability_score):
    if auto_fixable:
        return "Yes"
    if fixability_score is not None and fixability_score >= 5:
        return "Maybe"
    return "No"

def _risk_label(risk):
    if not risk:
        return None
    return risk[0].upper() + risk[1:]

def _status_label(issue):
    if issue.get("triage_status") == "untriaged":
        return "Untriaged"
    if not issue.get("auto_fixable") and issue.get("triage_status") == "triaged":
        return "Needs Human"
    m = {
        "queued": "Devin Ready",
        "in_progress": "In Progress",
        "pr_open": "PR Open",
        "done": "Closed",
        "failed": "Needs Human",
        "paused": "In Progress",
    }
    return m.get(issue.get("dispatch_status", ""), "Untriaged")

def _find_page_by_issue_number(github_number):
    db_id = _get_db_id()
    if not db_id or not notion:
        return None
    results = notion.databases.query(
        database_id=db_id,
        filter={"property": "Issue #", "number": {"equals": github_number}},
    )
    return results["results"][0] if results["results"] else None

def _truncate(s, max_len=2000):
    if not s:
        return ""
    return s[:max_len] + "…" if len(s) > max_len else s


# ---- upsertIssueRow ----

async def upsert_issue_row(issue, triage, priority_rank):
    db_id = _get_db_id()
    if not db_id or not notion:
        print("[notion] NOTION_DATABASE_ID not set, skipping upsert")
        return

    affected = triage.get("affected_files", [])
    if isinstance(affected, str):
        try:
            affected = json.loads(affected)
        except Exception:
            affected = []
    affected_str = ", ".join(affected)

    days_open = 0
    if issue.get("created_at"):
        try:
            days_open = (datetime.utcnow() - parse_date(issue["created_at"]).replace(tzinfo=None)).days
        except Exception:
            pass

    props = {
        "Title": {"title": [{"text": {"content": f"#{issue.get('github_number')} {issue.get('title', '')}"}}]},
        "Issue #": {"number": issue.get("github_number")},
        "Priority Rank": {"number": priority_rank},
        "Priority Score": {"number": round(triage.get("priority_score", 0), 1)},
        "Fixability": {"number": triage.get("fixability_score")},
        "Impact": {"number": triage.get("impact_score")},
        "Auto-fixable": {"select": {"name": _auto_fixable_label(triage.get("auto_fixable"), triage.get("fixability_score"))}},
        "Status": {"select": {"name": _status_label({**issue, **triage})}},
        "Triage Summary": {"rich_text": [{"text": {"content": _truncate(triage.get("triage_summary", ""))}}]},
        "Affected Files": {"rich_text": [{"text": {"content": _truncate(affected_str)}}]},
        "Days Open": {"number": days_open},
        "PR Link": {"url": issue.get("pr_url")} if issue.get("pr_url") else {"url": None},
        "GitHub Link": {"url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue.get('github_number')}"} if GITHUB_OWNER else {"url": None},
        "Dispatched At": {"date": {"start": issue["dispatched_at"]}} if issue.get("dispatched_at") else {"date": None},
        "Completed At": {"date": {"start": issue["completed_at"]}} if issue.get("completed_at") else {"date": None},
    }

    complexity = _complexity_label(triage.get("complexity_score"))
    if complexity:
        props["Complexity"] = {"select": {"name": complexity}}
    risk = _risk_label(triage.get("risk_level"))
    if risk:
        props["Risk"] = {"select": {"name": risk}}

    try:
        existing = _find_page_by_issue_number(issue.get("github_number"))
        if existing:
            notion.pages.update(page_id=existing["id"], properties=props)
            print(f"[notion] Updated row for #{issue.get('github_number')}")
        else:
            notion.pages.create(parent={"database_id": db_id}, properties=props)
            print(f"[notion] Created row for #{issue.get('github_number')}")
    except Exception as e:
        print(f"[notion] upsertIssueRow failed for #{issue.get('github_number')}: {e}")


# ---- updateIssueStatus ----

async def update_issue_status(github_number, status, extra_props=None):
    db_id = _get_db_id()
    if not db_id or not notion:
        return
    extra_props = extra_props or {}
    try:
        existing = _find_page_by_issue_number(github_number)
        if not existing:
            return
        props = {"Status": {"select": {"name": status}}}
        if extra_props.get("prLink"):
            props["PR Link"] = {"url": extra_props["prLink"]}
        if extra_props.get("dispatchedAt"):
            props["Dispatched At"] = {"date": {"start": extra_props["dispatchedAt"]}}
        if extra_props.get("completedAt"):
            props["Completed At"] = {"date": {"start": extra_props["completedAt"]}}
        notion.pages.update(page_id=existing["id"], properties=props)
        print(f"[notion] Status updated for #{github_number} → {status}")
    except Exception as e:
        print(f"[notion] updateIssueStatus failed for #{github_number}: {e}")


# ---- syncNotionStats ----

async def sync_notion_stats(stats):
    db_id = _get_db_id()
    if not db_id or not notion:
        return
    try:
        db = notion.databases.retrieve(database_id=db_id)
        parent_id = (db.get("parent") or {}).get("page_id")
        if not parent_id:
            return

        blocks = notion.blocks.children.list(block_id=parent_id)
        for block in blocks.get("results", []):
            if block.get("type") == "callout":
                text = (block.get("callout", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""))
                if "Open Issues" in text or "Stats update" in text:
                    notion.blocks.delete(block_id=block["id"])

        stats_text = (
            f"📊  Open Issues: {stats.get('total_open', 0)}  ·  "
            f"Devin Ready: {stats.get('devin_ready', 0)}  ·  "
            f"In Progress: {stats.get('in_progress', 0)}  ·  "
            f"PRs Open: {stats.get('prs_open', 0)}  ·  "
            f"Closed This Week: {stats.get('closed_this_week', 0)}  ·  "
            f"Est. Hours Saved: ~{(stats.get('closed_this_week', 0)) * 3}h"
        )
        notion.blocks.children.append(block_id=parent_id, children=[_callout_block(stats_text)])
        print("[notion] Stats synced to parent page")
    except Exception as e:
        print(f"[notion] syncNotionStats failed: {e}")


# ---- createWeeklyDigest ----

async def create_weekly_digest(stats, completed_issues=None, needs_human_issues=None):
    db_id = _get_db_id()
    if not db_id or not notion:
        return
    completed_issues = completed_issues or []
    needs_human_issues = needs_human_issues or []

    db = notion.databases.retrieve(database_id=db_id)
    parent_id = (db.get("parent") or {}).get("page_id")

    week_of = datetime.now().strftime("%B %d, %Y")
    children = [
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Summary"}}]}},
        _bullet(f"Issues triaged this week: {stats.get('total_open', 0)}"),
        _bullet(f"Dispatched to Devin: {stats.get('in_progress', 0)}"),
        _bullet(f"PRs opened: {stats.get('prs_open', 0)}"),
        _bullet(f"Issues closed: {stats.get('closed_this_week', 0)}"),
        _bullet(f"Est. eng hours saved: ~{(stats.get('closed_this_week', 0)) * 3}h"),
        _divider_block(),
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Top Wins"}}]}},
    ]
    if not completed_issues:
        children.append(_bullet("No completed issues this week."))
    else:
        for iss in completed_issues:
            children.append(_bullet(f"#{iss.get('github_number')} {iss.get('title', '')}"))
    children.append(_divider_block())
    children.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Still in Queue — Needs Human"}}]}})
    if not needs_human_issues:
        children.append(_bullet("All clear — no issues needing human attention."))
    else:
        for iss in needs_human_issues:
            children.append(_bullet(f"#{iss.get('github_number')} {iss.get('title', '')} — {iss.get('needs_human_reason', 'Requires human judgment')}"))

    try:
        parent = {"page_id": parent_id} if parent_id else {"database_id": db_id}
        notion.pages.create(
            parent=parent,
            properties={"title": {"title": [{"text": {"content": f"Week of {week_of} — Devin Autopilot Summary"}}]}},
            children=children,
        )
        print(f"[notion] Weekly digest created for week of {week_of}")
    except Exception as e:
        print(f"[notion] createWeeklyDigest failed: {e}")


def _bullet(text):
    return {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

def _callout_block(text):
    return {"object": "block", "type": "callout", "callout": {"icon": {"type": "emoji", "emoji": "📊"}, "rich_text": [{"type": "text", "text": {"content": text}}]}}

def _divider_block():
    return {"object": "block", "type": "divider", "divider": {}}
