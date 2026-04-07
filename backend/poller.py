from __future__ import annotations
import re
import httpx
from datetime import datetime

from config import DEVIN_API_KEY
from db import get_active_sessions, get_pr_open_issues, update_dispatch, log_activity
from github_client import post_issue_comment, add_labels, remove_label, get_pr_status
from templates import session_completed_comment, session_failed_comment, slack_pr_ready, slack_stuck
from slack_client import send_slack_message


async def _fetch_devin_session(session_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.devin.ai/v1/sessions/{session_id}",
            headers={"Authorization": f"Bearer {DEVIN_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


def _extract_pr_info(session: dict) -> tuple:
    """Extract PR URL and number from session — checks top-level fields AND messages."""
    pr_url = None
    pr_number = None

    # Check top-level fields first
    pr_url = session.get("pr_url") or (session.get("pull_request") or {}).get("url") or (session.get("result") or {}).get("pr_url")
    pr_number = session.get("pr_number") or (session.get("pull_request") or {}).get("number")

    # If not found, scan messages for PR links (Devin often reports PRs in messages)
    if not pr_url:
        for msg in session.get("messages", []):
            if msg.get("type") == "initial_user_message":
                continue
            text = msg.get("message", "")
            match = re.search(r"https://github\.com/[^/]+/[^/]+/pull/(\d+)", text)
            if match:
                pr_url = match.group(0)
                pr_number = int(match.group(1))
                break

    if pr_url and not pr_number:
        match = re.search(r"/pull/(\d+)", pr_url)
        if match:
            pr_number = int(match.group(1))
    return pr_url, pr_number


def _is_session_done(session: dict) -> str | None:
    """Check if session is done. Returns 'completed', 'failed', or None."""
    status = (session.get("status") or "").lower()
    status_enum = (session.get("status_enum") or "").lower()

    # Completed states
    if status in ("completed", "success", "finished") or status_enum in ("completed", "success", "finished"):
        return "completed"

    # Failed states
    if status in ("failed", "error", "stuck") or status_enum in ("failed", "error", "stuck"):
        return "failed"

    # Check if Devin posted a PR link in messages (session may still be "running" or "blocked")
    pr_url, _ = _extract_pr_info(session)
    if pr_url:
        return "completed"

    return None


async def poll_active_devin_sessions():
    active = get_active_sessions()
    if active:
        print(f"[poller] Checking {len(active)} active session(s)")

    for issue in active:
        try:
            session = await _fetch_devin_session(issue["devin_session_id"])
            result = _is_session_done(session)

            if result == "completed":
                pr_url, pr_number = _extract_pr_info(session)
                print(f"[poller] #{issue['github_number']} completed — PR: {pr_url}")
                update_dispatch(issue["github_number"], {
                    "dispatch_status": "pr_open" if pr_url else "done",
                    "pr_url": pr_url,
                    "pr_number": pr_number,
                    "completed_at": datetime.utcnow().isoformat(),
                })

                try:
                    await post_issue_comment(issue["github_number"], session_completed_comment(issue, pr_url, pr_number))
                    await remove_label(issue["github_number"], "devin-in-progress")
                    await add_labels(issue["github_number"], ["devin-done"])
                    msg = slack_pr_ready(issue, pr_url, pr_number)
                    await send_slack_message(msg)
                except Exception as e:
                    print(f"[poller] GitHub/Slack update failed for #{issue['github_number']}: {e}")

                # Notion
                try:
                    from notion_client_mod import update_issue_status
                    await update_issue_status(issue["github_number"], "PR Open", {"prLink": pr_url, "completedAt": datetime.utcnow().isoformat()})
                except Exception as e:
                    print(f"[poller] Notion update failed for #{issue['github_number']}: {e}")

                log_activity(issue["github_number"], "pr_opened", f"Devin opened PR{f' #{pr_number}' if pr_number else ''} for issue #{issue['github_number']}")

            elif result == "failed":
                reason = session.get("failure_reason") or session.get("error")
                print(f"[poller] #{issue['github_number']} failed: {reason}")
                update_dispatch(issue["github_number"], {
                    "dispatch_status": "failed",
                    "failure_reason": reason,
                    "completed_at": datetime.utcnow().isoformat(),
                })

                try:
                    await post_issue_comment(issue["github_number"], session_failed_comment(issue, reason))
                    await remove_label(issue["github_number"], "devin-in-progress")
                    await add_labels(issue["github_number"], ["needs-human"])
                    msg = slack_stuck(issue, reason)
                    await send_slack_message(msg)
                except Exception as e:
                    print(f"[poller] GitHub/Slack update failed for #{issue['github_number']}: {e}")

                try:
                    from notion_client_mod import update_issue_status
                    await update_issue_status(issue["github_number"], "Needs Human")
                except Exception as e:
                    print(f"[poller] Notion update failed for #{issue['github_number']}: {e}")

                log_activity(issue["github_number"], "failed", f"Devin got stuck on issue #{issue['github_number']}")
            else:
                status_enum = session.get("status_enum", "unknown")
                print(f"[poller] #{issue['github_number']} still active (status_enum: {status_enum})")
        except Exception as e:
            print(f"[poller] Error polling session for #{issue['github_number']}: {e}")

    # Check if any open PRs have been merged
    pr_open = get_pr_open_issues()
    for issue in pr_open:
        try:
            status = await get_pr_status(issue["pr_number"])
            if status == "merged":
                print(f"[poller] #{issue['github_number']} PR #{issue['pr_number']} merged!")
                update_dispatch(issue["github_number"], {"dispatch_status": "done"})
                log_activity(issue["github_number"], "completed", f"PR #{issue['pr_number']} merged for issue #{issue['github_number']}")
                try:
                    await remove_label(issue["github_number"], "devin-done")
                    await add_labels(issue["github_number"], ["resolved"])
                except Exception:
                    pass
            elif status == "closed":
                print(f"[poller] #{issue['github_number']} PR #{issue['pr_number']} closed without merge")
                update_dispatch(issue["github_number"], {"dispatch_status": "failed", "failure_reason": "PR closed without merge"})
                log_activity(issue["github_number"], "failed", f"PR #{issue['pr_number']} closed without merge")
        except Exception as e:
            print(f"[poller] Error checking PR for #{issue['github_number']}: {e}")
