import json
from datetime import datetime
from config import DASHBOARD_URL, GITHUB_OWNER, GITHUB_REPO

# ---- GitHub comment templates ----

def triage_comment(issue, triage, priority_rank):
    fix_icon = "✅" if triage.get("auto_fixable") else "🔶"
    risk_icons = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    risk_icon = risk_icons.get(triage.get("risk_level", ""), "⚪️")

    files = triage.get("affected_files", [])
    if isinstance(files, str):
        try:
            files = json.loads(files)
        except Exception:
            files = []

    files_str = ", ".join(f"`{f}`" for f in files)
    gn = issue.get("github_number")

    dispatch_block = (
        f"""**To dispatch to Devin:**
- Add the `dispatch-devin` label to this issue, or
- Use `/devin dispatch #{gn}` in Slack, or
- Click Dispatch on the [dashboard]({DASHBOARD_URL})"""
        if triage.get("auto_fixable")
        else f"""**Why this needs a human:**
{triage.get('needs_human_reason', '')}"""
    )

    return f"""## 🤖 Devin Triage Report

**Priority rank in queue:** #{priority_rank}
**Auto-fixable:** {fix_icon} {"Yes" if triage.get("auto_fixable") else "No"}
**Risk:** {risk_icon} {triage.get("risk_level", "")}

| | |
|---|---|
| Fixability | {triage.get("fixability_score", "—")}/10 |
| Impact | {triage.get("impact_score", "—")}/10 |
| Complexity | {triage.get("complexity_score", "—")}/10 |
| Affected files | {files_str} |

**What needs to happen:**
{triage.get("triage_summary", "")}

{dispatch_block}

---
*Triaged by Devin Autopilot · [View dashboard]({DASHBOARD_URL})*"""


def session_started_comment(issue):
    gn = issue.get("github_number")
    return f"""## 🤖 Devin is working on this

Session started · Devin is working autonomously on the fix.

[Watch live on dashboard]({DASHBOARD_URL}/issues/{gn})

---
*Will update this thread when complete or if it needs help*"""


def session_completed_comment(issue, pr_url, pr_number):
    gn = issue.get("github_number")
    return f"""## ✅ Devin opened a PR

**PR #{pr_number} is ready for review.**

{pr_url}

Devin completed the fix. Please review when you have a moment — if everything looks good, merge and this issue will close automatically.

[View PR]({pr_url}) · [View session log]({DASHBOARD_URL}/issues/{gn})

---
*Ready for human review · Opened by Devin Autopilot*"""


def session_failed_comment(issue, failure_reason):
    gn = issue.get("github_number")
    reason = failure_reason or "The fix required context or judgment that wasn't available in the issue description."
    return f"""## ⚠️ Devin got stuck

Devin attempted a fix but wasn't able to complete it confidently.

**What happened:**
{reason}

**Suggested next step:**
A senior engineer should review the issue. You can add more context as a comment and re-dispatch, or assign it directly to your team.

[View session log]({DASHBOARD_URL}/issues/{gn})

---
*Escalated by Devin Autopilot*"""


# ---- Slack message templates ----

def slack_session_started(issue):
    gn = issue.get("github_number")
    return {
        "channel": None,  # filled by caller
        "text": f"🤖 Devin started working on issue #{gn}",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🤖 Devin started working*\n*Issue #{gn}:* {issue.get('title', '')}\n\nEstimated time: 15–30 min · No action needed"},
            },
            {
                "type": "actions",
                "elements": [{"type": "button", "text": {"type": "plain_text", "text": "Watch live"}, "url": f"{DASHBOARD_URL}/issues/{gn}"}],
            },
        ],
    }


def slack_pr_ready(issue, pr_url, pr_number):
    gn = issue.get("github_number")
    return {
        "channel": None,
        "text": f"✅ PR ready for review · Issue #{gn}",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*✅ PR ready for review*\n*Issue #{gn}:* {issue.get('title', '')}\n\nDevin opened PR #{pr_number} · tests passing"},
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Review PR"}, "url": pr_url},
                    {"type": "button", "text": {"type": "plain_text", "text": "View issue"}, "url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{gn}"},
                ],
            },
        ],
    }


def slack_stuck(issue, failure_reason):
    gn = issue.get("github_number")
    reason = failure_reason or "Devin found the fix is more complex than the issue description suggests."
    return {
        "channel": None,
        "text": f"⚠️ Devin needs help · Issue #{gn}",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*⚠️ Devin needs help*\n*Issue #{gn}:* {issue.get('title', '')}\n\n{reason}"},
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Add context to issue"}, "url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{gn}"},
                    {"type": "button", "text": {"type": "plain_text", "text": "View session log"}, "url": f"{DASHBOARD_URL}/issues/{gn}"},
                ],
            },
        ],
    }


def slack_morning_digest(stats):
    today = datetime.now().strftime("%A, %b %-d")
    oldest = f" (oldest: {stats.get('oldest_pr_hours')}h)" if stats.get("oldest_pr_hours") else ""
    hours_saved = (stats.get("closed_this_week", 0)) * 3
    return {
        "channel": None,
        "text": f"Good morning. Backlog digest for {today}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Good morning. Here's your backlog.*\n\n"
                        f"*Open issues:* {stats.get('total_open', 0)}\n"
                        f"*Devin ready:* {stats.get('devin_ready', 0)}\n"
                        f"*In progress:* {stats.get('in_progress', 0)}\n"
                        f"*PRs awaiting review:* {stats.get('prs_open', 0)}{oldest}\n"
                        f"*Closed this week:* {stats.get('closed_this_week', 0)}\n\n"
                        f"*Est. eng hours saved this week:* ~{hours_saved}h"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "View dashboard"}, "url": DASHBOARD_URL},
                    {"type": "button", "text": {"type": "plain_text", "text": "Review open PRs"}, "url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"},
                ],
            },
        ],
    }
