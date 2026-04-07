from __future__ import annotations

import logging
import httpx
from config import GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}
BASE = "https://api.github.com"

async def fetch_open_issues() -> list[dict]:
    """Fetch all open issues (excluding PRs) from the configured GitHub repo."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues",
            headers=HEADERS,
            params={"state": "open", "per_page": 100},
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "github_number": i["number"],
            "title": i["title"],
            "body": i.get("body") or "",
            "labels": [l["name"] if isinstance(l, dict) else l for l in i.get("labels", [])],
            "state": i["state"],
            "created_at": i["created_at"],
            "updated_at": i["updated_at"],
        }
        for i in data
        if "pull_request" not in i
    ]

async def post_issue_comment(issue_number: int, body: str) -> None:
    """Post a comment on a GitHub issue."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/comments",
            headers=HEADERS,
            json={"body": body},
        )
        resp.raise_for_status()

async def add_labels(issue_number: int, labels: list[str]) -> None:
    """Add labels to a GitHub issue."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/labels",
            headers=HEADERS,
            json={"labels": labels},
        )
        resp.raise_for_status()

async def remove_label(issue_number: int, label: str) -> None:
    """Remove a label from a GitHub issue. Silently ignores errors."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.delete(
                f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/labels/{label}",
                headers=HEADERS,
            )
        except Exception:
            pass

async def get_pr_status(pr_number: int) -> str:
    """Returns 'open', 'closed', or 'merged'."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{pr_number}",
            headers=HEADERS,
        )
        resp.raise_for_status()
        pr = resp.json()
        if pr.get("merged"):
            return "merged"
        return pr.get("state", "open")

async def has_label(issue_number: int, label: str) -> bool:
    """Check if a GitHub issue has a specific label."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/labels",
            headers=HEADERS,
        )
        resp.raise_for_status()
        return any(l["name"] == label for l in resp.json())
