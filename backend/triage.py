from __future__ import annotations

import asyncio
import logging
import json
import re
import httpx
from datetime import datetime
from dateutil.parser import parse as parse_date

from config import DEVIN_API_KEY, DEVIN_POLL_INTERVAL_SECONDS, DEVIN_TRIAGE_TIMEOUT_SECONDS
from db import upsert_issue, get_untriaged_issues, update_triage, get_all_issues_ranked, log_activity
from github_client import fetch_open_issues, post_issue_comment, add_labels
from templates import triage_comment

logger = logging.getLogger(__name__)

_triage_running = False
_triage_lock = asyncio.Lock()

async def _create_devin_session(prompt: str) -> dict:
    """Create a Devin session for triage analysis."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.devin.ai/v1/sessions",
            headers={"Authorization": f"Bearer {DEVIN_API_KEY}", "Content-Type": "application/json"},
            json={"prompt": prompt},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

async def _poll_devin_session(session_id: str) -> dict:
    """Poll a Devin session for its current state."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.devin.ai/v1/sessions/{session_id}",
            headers={"Authorization": f"Bearer {DEVIN_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

async def _wait_for_devin_response(session_id: str) -> str:
    """Poll a Devin session until it produces a triage response or times out."""
    start = asyncio.get_event_loop().time()
    last_status = ""
    last_msg_count = 0

    while asyncio.get_event_loop().time() - start < DEVIN_TRIAGE_TIMEOUT_SECONDS:
        session = await _poll_devin_session(session_id)
        status = (session.get("status") or session.get("status_enum") or "").lower()
        messages = session.get("messages") or []

        if status != last_status:
            logger.info("Session %s status: \"%s\" | messages: %d", session_id, status, len(messages))
            last_status = status

        # Check if Devin has replied in messages
        if len(messages) > last_msg_count:
            logger.debug("Messages changed: %d -> %d", last_msg_count, len(messages))
            last_msg_count = len(messages)
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                msg_type = (msg.get("type") or "").lower()
                if msg_type == "initial_user_message":
                    continue
                content = msg.get("message") or msg.get("content") or msg.get("text") or ""
                if content and ("issue_number" in content or "fixability_score" in content):
                    logger.info("Found triage response in message %d type=\"%s\" (%d chars)", i, msg_type, len(content))
                    return content

        # Check structured_output
        so = session.get("structured_output")
        if so:
            so_str = so if isinstance(so, str) else json.dumps(so)
            if "issue_number" in so_str or "fixability_score" in so_str:
                logger.info("Found triage response in structured_output")
                return so_str

        # Also check status_enum
        status_enum = (session.get("status_enum") or "").lower()
        terminal = {"completed", "success", "finished", "done", "stopped", "blocked"}
        if status in terminal or status_enum in terminal:
            logger.info("Terminal status: \"%s\" / enum: \"%s\"", status, status_enum)
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                if (msg.get("type") or "").lower() == "initial_user_message":
                    continue
                content = msg.get("message") or msg.get("content") or msg.get("text") or ""
                if content:
                    return content
            return json.dumps(session)

        failed = {"failed", "error", "cancelled"}
        if status in failed or status_enum in failed:
            raise Exception(f"Devin session failed: {session.get('failure_reason') or session.get('error') or status}")

        await asyncio.sleep(DEVIN_POLL_INTERVAL_SECONDS)

    raise Exception("Devin triage session timed out")


def _build_batch_prompt(issues: list[dict]) -> str:
    """Build the batch triage prompt for multiple issues."""
    blocks = []
    for issue in issues:
        labels = issue.get("labels", [])
        if isinstance(labels, str):
            try:
                labels = json.loads(labels)
            except Exception:
                labels = []
        created = issue.get("created_at", "")
        days_open = 0
        if created:
            try:
                days_open = (datetime.utcnow() - parse_date(created).replace(tzinfo=None)).days
            except Exception:
                pass
        blocks.append(
            f"--- Issue #{issue['github_number']} ---\n"
            f"Title: {issue['title']}\n"
            f"Body: {issue['body']}\n"
            f"Labels: {', '.join(labels)}\n"
            f"Days open: {days_open}"
        )

    issues_text = "\n\n".join(blocks)

    return f"""You are a senior software engineer triaging GitHub issues for a TypeScript/Rust monorepo built with Turborepo. The monorepo contains apps (agents, docs), shared packages (turbo-codemod, turbo-gen, turbo-ignore, turbo-utils, turbo-types, eslint-plugin-turbo, create-turbo, turbo-workspaces, turbo-vsc, turbo-releaser, turbo-repository, turbo-telemetry, turbo-test-utils, tsconfig), a CLI in Rust (crates/), and various config/build tooling.

Analyze ALL of the following issues and return a JSON array with one object per issue. You should lean toward marking issues as auto_fixable — an AI coding agent (Devin) is highly capable and can handle multi-file changes, write tests, update configs, fix bugs, add features, update docs, and refactor code. Only mark auto_fixable: false if the issue truly requires human product judgment, ambiguous architectural decisions, or changes to critical security/payment flows.

{issues_text}

Return ONLY a valid JSON array with one object per issue, in the same order as above. No markdown fences, no explanation, just the raw JSON array.

Each object must have these fields:
{{
  "issue_number": <the GitHub issue number>,
  "fixability_score": <0-10, how autonomously fixable without human judgment>,
  "impact_score": <0-10, how many users or systems affected>,
  "complexity_score": <0-10, higher means more complex>,
  "risk_level": <"low" | "medium" | "high">,
  "auto_fixable": <true | false>,
  "affected_files": <array of likely file paths based on the description, be specific>,
  "triage_summary": <one sentence: what exactly needs to be done, plain English, no jargon>,
  "devin_instructions": <if auto_fixable true: 2-3 sentences of specific step-by-step instructions for an AI coding agent. If auto_fixable false: null>,
  "needs_human_reason": <if auto_fixable false: one sentence explaining why a human is needed. If auto_fixable true: null>
}}

Scoring guidance:
- fixability 8-10: config file changes, removing unused code, adding null checks, clear isolated fixes, documentation updates, adding flags/options, error message improvements
- fixability 5-7: multi-file changes that are well-scoped, adding new features with clear requirements, refactoring with clear before/after
- fixability 0-4: requires product/design decisions, unclear requirements, touches core auth or payment logic
- auto_fixable = true IF fixability >= 3 — Devin is highly capable and can handle most engineering tasks
- auto_fixable = false ONLY IF fixability < 3 OR the issue requires subjective product decisions that an engineer must make
- risk_level "high" ONLY if the change touches authentication, payments, data migrations, or could cause data loss
- risk_level "medium" for shared infrastructure, cross-cutting changes
- risk_level "low" for isolated package changes, docs, config, tests, most bug fixes

IMPORTANT: Most well-described bugs and feature requests ARE auto-fixable. Err on the side of auto_fixable: true. Return ONLY the JSON array. No other text. Do NOT ask any follow-up questions or wait for confirmation — just output the JSON array and stop."""


def _compute_scores(triage: dict, issue: dict) -> None:
    """Compute staleness and composite priority scores for a triaged issue."""
    created = issue.get("created_at", "")
    days_open = 0
    if created:
        try:
            days_open = (datetime.utcnow() - parse_date(created).replace(tzinfo=None)).days
        except Exception:
            pass
    triage["staleness_score"] = min(10, days_open // 9)
    complexity_inverse = 10 - (triage.get("complexity_score") or 0)
    triage["priority_score"] = (
        (triage.get("fixability_score", 0) * 0.4)
        + (triage.get("impact_score", 0) * 0.3)
        + (triage["staleness_score"] * 0.2)
        + (complexity_inverse * 0.1)
    )


async def fetch_and_triage_new_issues() -> None:
    """Fetch open issues from GitHub, triage untriaged ones via Devin."""
    global _triage_running
    async with _triage_lock:
        if _triage_running:
            logger.info("Already running, skipping this cycle")
            return
        _triage_running = True
    logger.info("Fetching open issues from GitHub...")
    try:
        issues = await fetch_open_issues()
        for issue in issues:
            upsert_issue(issue)

        untriaged = get_untriaged_issues()
        if not untriaged:
            logger.info("No untriaged issues")
            return
        BATCH_SIZE = 10
        logger.info("%d untriaged issues — processing in batches of %d", len(untriaged), BATCH_SIZE)

        # Try importing notion — optional
        try:
            from notion_client_mod import upsert_issue_row
        except Exception:
            upsert_issue_row = None

        for batch_start in range(0, len(untriaged), BATCH_SIZE):
            batch = untriaged[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (len(untriaged) + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info("Batch %d/%d — triaging %d issues (#%s)", batch_num, total_batches, len(batch), ", #".join(str(i["github_number"]) for i in batch))

            # Rate limit: wait between batches to avoid 429s from Devin API
            if batch_start > 0:
                logger.info("Waiting 30s between batches for rate limits...")
                await asyncio.sleep(30)

            try:
                prompt = _build_batch_prompt(batch)
                session = await _create_devin_session(prompt)
                session_id = session.get("id") or session.get("session_id")
                logger.info("Devin session %s created for batch %d, polling...", session_id, batch_num)

                raw = await _wait_for_devin_response(session_id)

                # Close the triage session so it doesn't count against concurrent limit
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"https://api.devin.ai/v1/sessions/{session_id}/cancel",
                            headers={"Authorization": f"Bearer {DEVIN_API_KEY}"},
                            timeout=10,
                        )
                    logger.info("Closed triage session %s", session_id)
                except Exception as e:
                    logger.debug("Could not close triage session %s: %s", session_id, e)

                # Extract JSON array
                json_str = raw.strip()
                fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", json_str)
                if fence_match:
                    json_str = fence_match.group(1)
                bracket_match = re.search(r"\[[\s\S]*\]", json_str)
                if bracket_match:
                    json_str = bracket_match.group(0)

                triage_results = json.loads(json_str)
                if not isinstance(triage_results, list):
                    raise Exception("Devin response is not a JSON array")

                logger.info("Batch %d: got %d triage results from Devin", batch_num, len(triage_results))
                triage_map = {t["issue_number"]: t for t in triage_results}

                for issue in batch:
                    try:
                        triage = triage_map.get(issue["github_number"])
                        if not triage:
                            logger.warning("No result for #%d in Devin response", issue['github_number'])
                            continue

                        _compute_scores(triage, issue)
                        update_triage(issue["github_number"], triage)

                        ranked = get_all_issues_ranked()
                        rank = next((i + 1 for i, r in enumerate(ranked) if r["github_number"] == issue["github_number"]), 0)

                        updated = {**issue, **triage, "affected_files": json.dumps(triage.get("affected_files", []))}
                        await post_issue_comment(issue["github_number"], triage_comment(updated, updated, rank))

                        labels_to_add = ["devin-ready"] if triage.get("auto_fixable") else ["needs-human"]
                        await add_labels(issue["github_number"], labels_to_add)

                        if upsert_issue_row:
                            try:
                                await upsert_issue_row(updated, triage, rank)
                            except Exception as e:
                                logger.error("Notion upsert failed for #%d: %s", issue['github_number'], e)

                        fix_label = "auto-fixable" if triage.get("auto_fixable") else "needs human review"
                        log_activity(
                            issue["github_number"],
                            "triaged",
                            f"Issue analyzed and triaged — ranked #{rank} in queue. Fixability {triage.get('fixability_score', '?')}/10, complexity {triage.get('complexity_score', '?')}/10, risk {triage.get('risk_level', 'unknown')}. Classified as {fix_label}.",
                        )
                        logger.info("#%d scored: priority=%.1f auto_fixable=%s", issue['github_number'], triage['priority_score'], triage.get('auto_fixable'))
                    except Exception as e:
                        logger.error("Failed to process #%d: %s", issue['github_number'], e)
            except Exception as e:
                logger.error("Batch %d failed: %s", batch_num, e)
                continue
    except Exception as e:
        logger.error("fetchAndTriageNewIssues error: %s", e)
    finally:
        _triage_running = False
