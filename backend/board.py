import httpx
from config import GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, GITHUB_PROJECT_ID
from db import get_all_issues_ranked

STATUS_TO_COLUMN = {
    "untriaged": "Untriaged",
    "queued": "Devin Ready",
    "needs_human": "Needs Human",
    "in_progress": "In Progress",
    "pr_open": "PR Open",
    "done": "Closed",
    "failed": "Needs Human",
}

_cached_field_meta = None

async def _graphql(query: str, variables: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.github.com/graphql",
            headers={"Authorization": f"bearer {GITHUB_TOKEN}"},
            json={"query": query, "variables": variables or {}},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

async def _load_field_meta():
    global _cached_field_meta
    if _cached_field_meta:
        return _cached_field_meta
    query = """
    query($project: ID!) {
      node(id: $project) {
        ... on ProjectV2 {
          fields(first: 20) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
            }
          }
        }
      }
    }
    """
    res = await _graphql(query, {"project": GITHUB_PROJECT_ID})
    fields = res.get("data", {}).get("node", {}).get("fields", {}).get("nodes", [])
    status_field = next((f for f in fields if f and f.get("name") == "Status"), None)
    if not status_field:
        raise Exception("Project has no Status field")
    _cached_field_meta = status_field
    return status_field

async def sync_github_project_board():
    if not GITHUB_PROJECT_ID:
        print("[board] GITHUB_PROJECT_ID not set, skipping board sync")
        return
    try:
        status_field = await _load_field_meta()
        issues = get_all_issues_ranked()

        # Get all project items
        query = """
        query($project: ID!) {
          node(id: $project) {
            ... on ProjectV2 {
              items(first: 100) {
                nodes { id content { ... on Issue { id number } } }
              }
            }
          }
        }
        """
        res = await _graphql(query, {"project": GITHUB_PROJECT_ID})
        items = res.get("data", {}).get("node", {}).get("items", {}).get("nodes", [])
        item_map = {n.get("content", {}).get("number"): n["id"] for n in items if n.get("content")}

        for issue in issues:
            logical_status = issue.get("dispatch_status") or "queued"
            if issue.get("triage_status") == "untriaged":
                logical_status = "untriaged"
            if not issue.get("auto_fixable") and issue.get("triage_status") == "triaged":
                logical_status = "needs_human"

            column_name = STATUS_TO_COLUMN.get(logical_status)
            option = next((o for o in status_field.get("options", []) if o["name"] == column_name), None)
            if not option:
                continue

            item_id = item_map.get(issue["github_number"])
            if not item_id:
                continue

            mutation = """
            mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) {
              updateProjectV2ItemFieldValue(input: {
                projectId: $project, itemId: $item, fieldId: $field,
                value: { singleSelectOptionId: $option }
              }) { projectV2Item { id } }
            }
            """
            await _graphql(mutation, {
                "project": GITHUB_PROJECT_ID,
                "item": item_id,
                "field": status_field["id"],
                "option": option["id"],
            })
        print("[board] Board sync complete")
    except Exception as e:
        print(f"[board] Sync error: {e}")
