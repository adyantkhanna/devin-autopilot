import asyncio
import json
import re
import httpx
from datetime import datetime
from dateutil.parser import parse as parse_date

from config import DEVIN_API_KEY
from db import upsert_issue, get_untriaged_issues, update_triage, get_all_issues_ranked, log_activity
from github_client import fetch_open_issues, post_issue_comment, add_labels
from templates import triage_comment

DEVIN_POLL_INTERVAL = 2  # seconds
DEVIN_TRIAGE_TIMEOUT = 900  # 15 minutes

_triage_running = False

async def _create_devin_session(prompt: str) -> dict:
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
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.devin.ai/v1/sessions/{session_id}",
            headers={"Authorization": f"Bearer {DEVIN_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

async def _wait_for_devin_response(session_id: str) -> str:
    start = asyncio.get_event_loop().time()
    last_status = ""
    last_msg_count = 0

    while asyncio.get_event_loop().time() - start < DEVIN_TRIAGE_TIMEOUT:
        session = await _poll_devin_session(session_id)
        status = (session.get("status") or session.get("status_enum") or "").lower()
        messages = session.get("messages") or []

        if status != last_status:
            print(f"[triage] Session {session_id} status: \"{status}\" | messages: {len(messages)}")
            last_status = status

        # Check if Devin has replied in messages
        if len(messages) > last_msg_count:
            print(f"[triage] Messages changed: {last_msg_count} → {len(messages)}")
            last_msg_count = len(messages)
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                msg_type = (msg.get("type") or "").lower()
                if msg_type == "initial_user_message":
                    continue
                content = msg.get("message") or msg.get("content") or msg.get("text") or ""
                if content and ("issue_number" in content or "fixability_score" in content):
                    print(f"[triage] Found triage response in message {i} type=\"{msg_type}\" ({len(content)} chars)")
                    return content

        # Check structured_output
        so = session.get("structured_output")
        if so:
            so_str = so if isinstance(so, str) else json.dumps(so)
            if "issue_number" in so_str or "fixability_score" in so_str:
                print("[triage] Found triage response in structured_output")
                return so_str

        # Also check status_enum
        status_enum = (session.get("status_enum") or "").lower()
        terminal = {"completed", "success", "finished", "done", "stopped", "blocked"}
        if status in terminal or status_enum in terminal:
            print(f"[triage] Terminal status: \"{status}\" / enum: \"{status_enum}\"")
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

        await asyncio.sleep(DEVIN_POLL_INTERVAL)

    raise Exception("Devin triage session timed out")


def _build_batch_prompt(issues: list[dict]) -> str:
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

    return f"""You are a senior software engineer triaging GitHub issues for a TypeScript monorepo built with Turborepo. The monorepo has multiple apps and shared packages.

Analyze ALL of the following issues and return a JSON array with one object per issue. Be conservative about what an AI coding agent can fix autonomously — only mark auto_fixable: true if you are confident it can be resolved without human judgment or design decisions.

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
- fixability 8-10: config file changes, removing unused code, adding null checks, clear isolated one-file fixes with no ambiguity
- fixability 5-7: multi-file changes that are still well-scoped, clear requirements
- fixability 0-4: requires design decisions, unclear requirements, touches authentication, payments, or core business logic
- auto_fixable = true ONLY IF fixability >= 7 AND risk_level = "low"
- risk_level "high" if the change touches auth, payments, data migrations, or shared infrastructure

IMPORTANT: Return ONLY the JSON array. No other text."""


def _compute_scores(triage: dict, issue: dict):
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


async def fetch_and_triage_new_issues():
    global _triage_running
    if _triage_running:
        print("[triage] Already running, skipping this cycle")
        return
    _triage_running = True
    print("[triage] Fetching open issues from GitHub...")
    try:
        issues = await fetch_open_issues()
        for issue in issues:
            upsert_issue(issue)

        untriaged = get_untriaged_issues()
        if not untriaged:
            print("[triage] No untriaged issues")
            return
        print(f"[triage] {len(untriaged)} untriaged issues — sending batch to Devin")

        prompt = _build_batch_prompt(untriaged)

        print("[triage] Creating single Devin session for all issues...")
        session = await _create_devin_session(prompt)
        session_id = session.get("id") or session.get("session_id")
        print(f"[triage] Devin session {session_id} created, polling...")

        raw = await _wait_for_devin_response(session_id)

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

        print(f"[triage] Got {len(triage_results)} triage results from Devin")

        triage_map = {t["issue_number"]: t for t in triage_results}

        # Try importing notion — optional
        try:
            from notion_client_mod import upsert_issue_row
        except Exception:
            upsert_issue_row = None

        for issue in untriaged:
            try:
                triage = triage_map.get(issue["github_number"])
                if not triage:
                    print(f"[triage] No result for #{issue['github_number']} in Devin response")
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
                        print(f"[triage] Notion upsert failed for #{issue['github_number']}: {e}")

                log_activity(
                    issue["github_number"],
                    "triaged",
                    f"Issue #{issue['github_number']} triaged — ranked #{rank} in queue ({'auto-fixable' if triage.get('auto_fixable') else 'needs human'})",
                )
                print(f"[triage] #{issue['github_number']} scored: priority={triage['priority_score']:.1f} auto_fixable={triage.get('auto_fixable')}")
            except Exception as e:
                print(f"[triage] Failed to process #{issue['github_number']}: {e}")
    except Exception as e:
        print(f"[triage] fetchAndTriageNewIssues error: {e}")
    finally:
        _triage_running = False
