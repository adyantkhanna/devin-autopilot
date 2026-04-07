from __future__ import annotations

import logging
import json
import httpx
from datetime import datetime

from config import DEVIN_API_KEY, GITHUB_OWNER, GITHUB_REPO
from db import get_issue, update_dispatch, log_activity, get_next_queued_for_autopilot, get_config
from github_client import post_issue_comment, add_labels, remove_label
from templates import session_started_comment, slack_session_started
from slack_client import send_slack_message

logger = logging.getLogger(__name__)


def build_devin_prompt(issue: dict) -> str:
    """Build the full prompt sent to Devin for resolving an issue."""
    affected_files: list[str] = []
    try:
        affected_files = json.loads(issue.get("affected_files") or "[]")
    except Exception:
        pass

    return f"""You are working on a TypeScript monorepo at: https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}

Your task is to resolve GitHub issue #{issue['github_number']}.

ISSUE TITLE:
{issue['title']}

ISSUE DESCRIPTION:
{issue['body']}

TRIAGE ANALYSIS:
{issue.get('triage_summary', '')}

LIKELY AFFECTED FILES:
{chr(10).join(affected_files)}

SPECIFIC INSTRUCTIONS:
{issue.get('devin_instructions', '')}

REQUIRED STEPS:
1. Clone the repository and read the affected files carefully before making any changes
2. Understand the full scope of the issue
3. Make the minimal change necessary to resolve the issue — do not over-engineer
4. Run existing tests to verify nothing is broken: npm test or turbo run test
5. If tests pass, open a pull request with:
   - Title prefixed with "fix:" or "feat:" matching the issue
   - Body must include "Closes #{issue['github_number']}"
   - Brief description of what you changed and why
   - Keep the diff minimal — do not refactor unrelated code

HARD CONSTRAINTS:
- Do not modify files outside the direct scope of this issue
- Do not add new dependencies unless the issue explicitly requires it
- If you discover the fix is more complex than described, or requires a design decision, stop and add a comment to the issue explaining what you found — do not guess
- When pushing to git, always use `git push --no-verify` to skip pre-push hooks (the repo has a husky hook that may fail in your environment)"""


async def create_devin_session(prompt: str) -> dict:
    """Create a new Devin AI session with the given prompt."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.devin.ai/v1/sessions",
            headers={"Authorization": f"Bearer {DEVIN_API_KEY}", "Content-Type": "application/json"},
            json={"prompt": prompt},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def dispatch_issue_by_number(github_number: int, triggered_by: str = "system", human_instructions: str | None = None) -> dict:
    """Dispatch an issue to Devin for autonomous resolution."""
    issue = get_issue(github_number)
    if not issue:
        raise Exception(f"Issue #{github_number} not found")
    if issue.get("dispatch_status") == "in_progress":
        logger.info("Issue #%d already in progress", github_number)
        return issue

    prompt = build_devin_prompt(issue)

    if human_instructions:
        prompt += f"""

HUMAN ENGINEER INSTRUCTIONS (HIGH PRIORITY — follow these carefully):
{human_instructions}"""
        log_activity(github_number, "human_instructions", f"Engineer added instructions: \"{human_instructions[:200]}\"", triggered_by)
    logger.info("Dispatching #%d to Devin...", github_number)

    session = await create_devin_session(prompt)
    session_id = session.get("id") or session.get("session_id")

    update_dispatch(github_number, {
        "dispatch_status": "in_progress",
        "devin_session_id": session_id,
        "devin_session_url": session.get("url"),
        "dispatched_at": datetime.utcnow().isoformat(),
    })

    try:
        await remove_label(github_number, "devin-ready")
        await remove_label(github_number, "dispatch-devin")
        await add_labels(github_number, ["devin-in-progress"])
    except Exception as e:
        logger.error("Label update failed for #%d: %s", github_number, e)

    try:
        await post_issue_comment(github_number, session_started_comment(issue))
    except Exception as e:
        logger.error("Comment failed for #%d: %s", github_number, e)

    try:
        msg = slack_session_started(issue)
        await send_slack_message(msg)
    except Exception as e:
        logger.error("Slack failed for #%d: %s", github_number, e)

    # Notion
    try:
        from notion_client_mod import update_issue_status
        await update_issue_status(github_number, "In Progress", {"dispatchedAt": datetime.utcnow().isoformat()})
    except Exception as e:
        logger.error("Notion update failed for #%d: %s", github_number, e)

    files = issue.get("affected_files", "[]")
    if isinstance(files, str):
        try:
            files = json.loads(files)
        except Exception:
            files = []
    files_str = ", ".join(files[:3]) if files else "not specified"
    log_activity(github_number, "dispatched", f"Devin session created and working autonomously. Targeting files: {files_str}. Triggered by {triggered_by}.", triggered_by)
    return {**issue, "session": session}


async def dispatch_next_in_queue() -> None:
    """Dispatch the next batch of queued issues in autopilot mode."""
    max_concurrent = int(get_config("autopilot_max_concurrent") or "2")
    next_issues = get_next_queued_for_autopilot(max_concurrent)
    for issue in next_issues:
        try:
            await dispatch_issue_by_number(issue["github_number"], "autopilot")
        except Exception as e:
            logger.error("Autopilot dispatch failed for #%d: %s", issue['github_number'], e)
