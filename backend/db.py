import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "devin-autopilot.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY,
        github_number INTEGER UNIQUE,
        title TEXT,
        body TEXT,
        labels TEXT,
        state TEXT,
        created_at TEXT,
        updated_at TEXT,
        triage_status TEXT DEFAULT 'untriaged',
        fixability_score INTEGER,
        impact_score INTEGER,
        staleness_score INTEGER,
        complexity_score INTEGER,
        priority_score REAL,
        affected_files TEXT,
        triage_summary TEXT,
        risk_level TEXT,
        auto_fixable INTEGER DEFAULT 0,
        devin_instructions TEXT,
        needs_human_reason TEXT,
        manual_priority_order INTEGER,
        override_by TEXT,
        override_at TEXT,
        dispatch_status TEXT DEFAULT 'queued',
        devin_session_id TEXT,
        devin_session_url TEXT,
        pr_url TEXT,
        pr_number INTEGER,
        failure_reason TEXT,
        dispatched_at TEXT,
        completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        github_number INTEGER,
        event_type TEXT,
        message TEXT,
        triggered_by TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)
    conn.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('mode', 'supervised')")
    conn.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('autopilot_max_concurrent', '2')")
    conn.commit()
    conn.close()

# ---- Config ----

def get_config(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM system_config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None

def set_config(key, value):
    conn = get_conn()
    conn.execute("INSERT INTO system_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
    conn.commit()
    conn.close()

# ---- Issues ----

def upsert_issue(issue):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM issues WHERE github_number = ?", (issue["github_number"],)).fetchone()
    labels_json = json.dumps(issue.get("labels", []))
    if existing:
        conn.execute(
            "UPDATE issues SET title=?, body=?, labels=?, state=?, updated_at=? WHERE github_number=?",
            (issue["title"], issue["body"], labels_json, issue["state"], issue["updated_at"], issue["github_number"])
        )
    else:
        conn.execute(
            "INSERT INTO issues (github_number, title, body, labels, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (issue["github_number"], issue["title"], issue["body"], labels_json, issue["state"], issue["created_at"], issue["updated_at"])
        )
    conn.commit()
    conn.close()

def get_issue(github_number):
    conn = get_conn()
    row = conn.execute("SELECT * FROM issues WHERE github_number = ?", (github_number,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_untriaged_issues():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM issues WHERE triage_status = 'untriaged' AND state = 'open'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_issues_ranked():
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM issues
        ORDER BY
            CASE WHEN manual_priority_order IS NULL THEN 1 ELSE 0 END,
            manual_priority_order ASC,
            priority_score DESC,
            github_number ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_triage(github_number, triage):
    conn = get_conn()
    conn.execute("""
        UPDATE issues SET
            triage_status = 'triaged',
            fixability_score = ?,
            impact_score = ?,
            staleness_score = ?,
            complexity_score = ?,
            priority_score = ?,
            affected_files = ?,
            triage_summary = ?,
            risk_level = ?,
            auto_fixable = ?,
            devin_instructions = ?,
            needs_human_reason = ?
        WHERE github_number = ?
    """, (
        triage.get("fixability_score"),
        triage.get("impact_score"),
        triage.get("staleness_score"),
        triage.get("complexity_score"),
        triage.get("priority_score"),
        json.dumps(triage.get("affected_files", [])),
        triage.get("triage_summary"),
        triage.get("risk_level"),
        1 if triage.get("auto_fixable") else 0,
        triage.get("devin_instructions"),
        triage.get("needs_human_reason"),
        github_number
    ))
    conn.commit()
    conn.close()

def update_dispatch(github_number, fields):
    allowed = ["dispatch_status", "devin_session_id", "devin_session_url", "pr_url", "pr_number", "failure_reason", "dispatched_at", "completed_at"]
    setters = []
    values = []
    for k in allowed:
        if k in fields:
            setters.append(f"{k} = ?")
            values.append(fields[k])
    if not setters:
        return
    values.append(github_number)
    conn = get_conn()
    conn.execute(f"UPDATE issues SET {', '.join(setters)} WHERE github_number = ?", values)
    conn.commit()
    conn.close()

def set_manual_priority(github_number, user):
    conn = get_conn()
    row = conn.execute("SELECT MIN(manual_priority_order) AS m FROM issues").fetchone()
    new_order = (row["m"] or 1) - 1
    conn.execute(
        "UPDATE issues SET manual_priority_order = ?, override_by = ?, override_at = datetime('now') WHERE github_number = ?",
        (new_order, user, github_number)
    )
    conn.commit()
    conn.close()


def reorder_issues(ordered_numbers: list, user: str):
    """Set manual_priority_order for all issues based on the given order."""
    conn = get_conn()
    for idx, github_number in enumerate(ordered_numbers):
        conn.execute(
            "UPDATE issues SET manual_priority_order = ?, override_by = ?, override_at = datetime('now') WHERE github_number = ?",
            (idx, user, github_number)
        )
    conn.commit()
    conn.close()

def get_active_sessions():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM issues WHERE dispatch_status IN ('in_progress') AND devin_session_id IS NOT NULL").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pr_open_issues():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM issues WHERE dispatch_status = 'pr_open' AND pr_number IS NOT NULL").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_next_queued_for_autopilot(limit=2):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM issues
        WHERE auto_fixable = 1 AND dispatch_status = 'queued' AND state = 'open'
        ORDER BY
            CASE WHEN manual_priority_order IS NULL THEN 1 ELSE 0 END,
            manual_priority_order ASC,
            priority_score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---- Activity log ----

def log_activity(github_number, event_type, message, triggered_by="system"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO activity_log (github_number, event_type, message, triggered_by) VALUES (?, ?, ?, ?)",
        (github_number, event_type, message, triggered_by)
    )
    conn.commit()
    conn.close()

def get_recent_activity(limit=50):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---- Stats ----

def get_stats(period: str = "7d"):
    period_map = {"24h": "-1 days", "7d": "-7 days", "30d": "-30 days", "all": "-9999 days"}
    interval = period_map.get(period, "-7 days")

    conn = get_conn()
    total_open = conn.execute("SELECT COUNT(*) AS c FROM issues WHERE state = 'open'").fetchone()["c"]
    devin_ready = conn.execute("SELECT COUNT(*) AS c FROM issues WHERE auto_fixable = 1 AND dispatch_status = 'queued' AND state = 'open'").fetchone()["c"]
    in_progress = conn.execute("SELECT COUNT(*) AS c FROM issues WHERE dispatch_status = 'in_progress'").fetchone()["c"]
    prs_open = conn.execute("SELECT COUNT(*) AS c FROM issues WHERE dispatch_status = 'pr_open'").fetchone()["c"]
    closed = conn.execute("SELECT COUNT(*) AS c FROM issues WHERE dispatch_status = 'done' AND completed_at >= datetime('now', ?)", (interval,)).fetchone()["c"]
    dispatched = conn.execute("SELECT COUNT(*) AS c FROM issues WHERE dispatched_at >= datetime('now', ?)", (interval,)).fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) AS c FROM issues WHERE dispatch_status = 'failed' AND completed_at >= datetime('now', ?)", (interval,)).fetchone()["c"]

    oldest_pr = conn.execute("SELECT MIN(completed_at) AS t FROM issues WHERE dispatch_status = 'pr_open'").fetchone()
    oldest_pr_hours = None
    if oldest_pr and oldest_pr["t"]:
        from dateutil.parser import parse
        oldest_pr_hours = int((datetime.utcnow() - parse(oldest_pr["t"])).total_seconds() / 3600)

    conn.close()
    period_label = {"24h": "today", "7d": "this week", "30d": "this month", "all": "all time"}.get(period, "this week")
    return {
        "total_open": total_open,
        "devin_ready": devin_ready,
        "in_progress": in_progress,
        "prs_open": prs_open,
        "closed": closed,
        "dispatched": dispatched,
        "failed": failed,
        "oldest_pr_hours": oldest_pr_hours,
        "period": period,
        "period_label": period_label,
    }

def get_completed_this_week():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM issues WHERE dispatch_status = 'done' AND completed_at >= datetime('now', '-7 days')").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_needs_human_issues():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM issues WHERE auto_fixable = 0 AND triage_status = 'triaged' AND state = 'open'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Init on import
init_db()
