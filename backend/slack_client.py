import httpx

from config import SLACK_BOT_TOKEN, SLACK_CHANNEL_ENG_ALERTS, SLACK_CHANNEL_DEVIN_OPS, DASHBOARD_URL, GITHUB_OWNER, GITHUB_REPO
from db import get_stats, get_all_issues_ranked, set_config, get_config, get_issue, set_manual_priority, log_activity, update_dispatch
from templates import slack_morning_digest


async def send_slack_message(payload: dict):
    if not payload.get("channel"):
        payload["channel"] = SLACK_CHANNEL_ENG_ALERTS

    if not SLACK_BOT_TOKEN:
        print(f"[slack] (mock) {payload.get('text', '')}")
        return {"ok": True, "mock": True}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
            json=payload,
        )
        return resp.json()


async def send_morning_digest():
    stats = get_stats()
    msg = slack_morning_digest(stats)
    msg["channel"] = SLACK_CHANNEL_DEVIN_OPS
    await send_slack_message(msg)


async def handle_slack_command(command: str, text: str, user_name: str, channel_id: str) -> str:
    args = (text or "").strip().split()
    if command != "/devin" or not args:
        return "Unknown command"

    action = args[0]

    try:
        if action == "status":
            period = args[1] if len(args) > 1 else "7d"
            stats = get_stats(period)
            mode = get_config("mode")
            issues = get_all_issues_ranked()
            period_label = stats.get("period_label", "this week")

            # Top 3 in-progress
            in_prog = [i for i in issues if i.get("dispatch_status") == "in_progress"]
            in_prog_lines = "\n".join(f"  • #{i['github_number']} {i['title'][:50]}" for i in in_prog[:3])
            if not in_prog_lines:
                in_prog_lines = "  _None right now_"

            # Top 3 PRs awaiting review
            prs = [i for i in issues if i.get("dispatch_status") == "pr_open"]
            pr_lines = "\n".join(f"  • #{i['github_number']} {i['title'][:50]} → <{i.get('pr_url', '#')}|PR>" for i in prs[:3])
            if not pr_lines:
                pr_lines = "  _None right now_"

            # Top 3 ready to dispatch
            ready = [i for i in issues if i.get("auto_fixable") and (i.get("dispatch_status") or "queued") == "queued"]
            ready_lines = "\n".join(f"  • #{i['github_number']} {i['title'][:50]}" for i in ready[:3])
            if not ready_lines:
                ready_lines = "  _Queue empty_"

            # Needs human
            human_count = len([i for i in issues if not i.get("auto_fixable") and (i.get("dispatch_status") or "queued") == "queued"])

            hours_saved = (stats.get("closed", 0)) * 3
            mode_emoji = "🟢" if mode == "autopilot" else "🟡"

            await send_slack_message({
                "channel": channel_id,
                "text": f"Devin Autopilot — Status Report",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "📊 Devin Autopilot — Status Report"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": (
                            f"*Mode:* {mode_emoji} {mode.title()}  ·  *Period:* {period_label}\n\n"
                            f"┌─────────────────────────────────┐\n"
                            f"│  *{stats.get('total_open', 0)}* open issues  ·  *{stats.get('devin_ready', 0)}* ready for Devin\n"
                            f"│  *{stats.get('in_progress', 0)}* in progress  ·  *{stats.get('prs_open', 0)}* PRs awaiting review\n"
                            f"│  *{stats.get('dispatched', 0)}* dispatched {period_label}  ·  *{stats.get('closed', 0)}* closed {period_label}\n"
                            f"│  *{human_count}* need human review  ·  *~{hours_saved}h* eng time saved\n"
                            f"└─────────────────────────────────┘"
                        )}
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*🔄 In Progress*\n{in_prog_lines}"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*👀 PRs Awaiting Review*\n{pr_lines}"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*⏳ Next Up (ready to dispatch)*\n{ready_lines}"}
                    },
                    {"type": "divider"},
                    {
                        "type": "actions",
                        "elements": [
                            {"type": "button", "text": {"type": "plain_text", "text": "📋 Open Dashboard"}, "url": DASHBOARD_URL},
                            {"type": "button", "text": {"type": "plain_text", "text": "🔀 Review PRs"}, "url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"},
                        ],
                    },
                ],
            })

        elif action == "queue":
            issues = get_all_issues_ranked()
            queued = [i for i in issues if (i.get("dispatch_status") or "queued") == "queued"]
            in_prog = [i for i in issues if i.get("dispatch_status") == "in_progress"]
            pr_open = [i for i in issues if i.get("dispatch_status") == "pr_open"]
            done = [i for i in issues if i.get("dispatch_status") == "done"]

            def fmt(i, idx=None):
                num = f"#{i['github_number']}"
                title = i['title'][:55]
                fix = "✅" if i.get("auto_fixable") else "🔶"
                rank = f"*{idx}.* " if idx else ""
                return f"{rank}{fix} {num} {title}"

            sections = []
            if in_prog:
                lines = "\n".join(fmt(i) for i in in_prog)
                sections.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*🔄 In Progress ({len(in_prog)})*\n{lines}"}})
            if pr_open:
                lines = "\n".join(f"👀 #{i['github_number']} {i['title'][:55]} → <{i.get('pr_url', '#')}|PR>" for i in pr_open)
                sections.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*👀 PRs Awaiting Review ({len(pr_open)})*\n{lines}"}})
            if queued:
                lines = "\n".join(fmt(i, idx+1) for idx, i in enumerate(queued[:10]))
                remaining = len(queued) - 10
                if remaining > 0:
                    lines += f"\n  _...and {remaining} more_"
                sections.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*⏳ Queued ({len(queued)})*\n{lines}"}})
            if done:
                sections.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*✅ Done:* {len(done)} issues resolved"}})

            await send_slack_message({
                "channel": channel_id,
                "text": f"Issue queue — {len(issues)} total",
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": f"📋 Issue Queue — {len(issues)} total"}},
                    *sections,
                    {"type": "divider"},
                    {
                        "type": "actions",
                        "elements": [
                            {"type": "button", "text": {"type": "plain_text", "text": "Open Dashboard"}, "url": DASHBOARD_URL},
                        ],
                    },
                ],
            })

        elif action == "prioritize":
            issue_number = int(args[1].replace("#", ""))
            set_manual_priority(issue_number, user_name)
            log_activity(issue_number, "prioritized", f"{user_name} moved issue #{issue_number} to top of queue", "slack_command")
            await send_slack_message({"channel": channel_id, "text": f"✅ Issue #{issue_number} moved to top of queue by @{user_name}"})

        elif action == "dispatch":
            issue_number = int(args[1].replace("#", ""))
            from dispatcher import dispatch_issue_by_number
            await dispatch_issue_by_number(issue_number, "slack_command")
            await send_slack_message({"channel": channel_id, "text": f"🤖 Dispatching issue #{issue_number} to Devin now..."})

        elif action == "stop":
            issue_number = int(args[1].replace("#", ""))
            issue = get_issue(issue_number)
            if issue and issue.get("devin_session_id"):
                async with httpx.AsyncClient() as client:
                    try:
                        await client.post(
                            f"https://api.devin.ai/v1/sessions/{issue['devin_session_id']}/pause",
                            headers={"Authorization": f"Bearer {__import__('config').DEVIN_API_KEY}"},
                        )
                    except Exception:
                        pass
            update_dispatch(issue_number, {"dispatch_status": "paused"})
            log_activity(issue_number, "paused", f"Devin session paused for issue #{issue_number}", "slack_command")
            await send_slack_message({"channel": channel_id, "text": f"⏸ Devin session paused for issue #{issue_number}"})

        elif action == "autopilot":
            mode = "autopilot" if len(args) > 1 and args[1] == "on" else "supervised"
            set_config("mode", mode)
            log_activity(None, "mode_change", f"Mode set to {mode} by {user_name}", "slack_command")
            text = (
                "🟢 Autopilot mode ON — Devin will dispatch issues automatically"
                if mode == "autopilot"
                else "🟡 Supervised mode ON — Devin will wait for human approval before dispatching"
            )
            await send_slack_message({"channel": channel_id, "text": text})

    except Exception as e:
        await send_slack_message({"channel": channel_id, "text": f"⚠️ Command failed: {e}"})

    return "Got it, working on it..."
