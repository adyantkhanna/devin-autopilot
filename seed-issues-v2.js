import { Octokit } from '@octokit/rest';

const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
const owner = process.env.GITHUB_OWNER;
const repo = 'finserv-monorepo';

const issues = [
  {
    title: "Missing error boundary in apps/agents root layout causes white screen on crash",
    body: `## Bug Report

If any component in \`apps/agents\` throws an unhandled error, the entire app unmounts with a blank white screen. No error message is shown to the user.

**File:** \`apps/agents/app/layout.tsx\`

**Current code:**
\`\`\`tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
\`\`\`

**Fix:** Wrap \`{children}\` in a React Error Boundary component that catches errors and shows a fallback UI with an error message and retry button.

**Impact:** Any unhandled error crashes the entire agents dashboard with no recovery path.`,
    labels: ["bug"]
  },
  {
    title: "apps/agents dashboard page missing loading state — shows empty page while fetching runs",
    body: `## Bug Report

The dashboard page at \`apps/agents/app/dashboard/page.tsx\` fetches run data on mount but shows nothing while loading. Users see a blank page until data arrives.

**File:** \`apps/agents/app/dashboard/page.tsx\`

**Current behavior:** The \`runs\` state starts as an empty array, and nothing renders until the fetch completes.

**Expected:** Show a loading skeleton or spinner while data is being fetched.

**Fix:** Add a \`loading\` state boolean, show a loading indicator while \`loading === true\`, set it to \`false\` after fetch completes.`,
    labels: ["bug", "enhancement"]
  },
  {
    title: "Hardcoded owner/repo in apps/agents/lib/github.ts should use environment variables",
    body: `## Bug Report

In \`apps/agents/lib/github.ts\`, the GitHub owner and repo are hardcoded:

\`\`\`ts
const OWNER = "vercel";
const REPO = "turborepo";
\`\`\`

This means the agents app can only work against the upstream repo, not forks or other deployments.

**Fix:** Read these from environment variables with fallback defaults:
\`\`\`ts
const OWNER = process.env.GITHUB_OWNER || "vercel";
const REPO = process.env.GITHUB_REPO || "turborepo";
\`\`\`

Also add \`GITHUB_OWNER\` and \`GITHUB_REPO\` to the env validation in \`apps/agents/lib/env.ts\`.

**Impact:** Agents app is unusable on any fork or custom deployment.`,
    labels: ["bug"]
  },
  {
    title: "apps/agents globals.css only imports tailwind — missing base reset styles",
    body: `## Bug Report

**File:** \`apps/agents/app/globals.css\`

Current contents:
\`\`\`css
@import "tailwindcss";
\`\`\`

This is missing basic reset styles that prevent layout inconsistencies across browsers. The body has default margins, font rendering isn't optimized, and box-sizing isn't set globally.

**Fix:** Add standard CSS reset rules:
\`\`\`css
@import "tailwindcss";

*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
\`\`\`

**Impact:** Minor visual inconsistencies across browsers in the agents dashboard.`,
    labels: ["bug"]
  },
  {
    title: "turbo.json test task has comments that break JSON5 strict parsers",
    body: `## Bug Report

\`turbo.json\` in the repo root contains JavaScript-style comments (\`//\`):

\`\`\`json
"test": {
  "outputs": ["coverage/**/*"],
  "env": ["NODE_VERSION"],
  // ^build is generically set here...
  "dependsOn": ["^build"]
},
\`\`\`

While Turbo supports JSON5 comments, this breaks strict JSON parsers and some CI tools that try to read \`turbo.json\`. Several external tools (renovatebot, dependabot, custom scripts) fail to parse this file.

**Fix:** Move the comments into the task descriptions or remove them, keeping the configuration equivalent.

**File:** \`turbo.json\` (root)`,
    labels: ["bug"]
  },
  {
    title: "apps/agents/lib/env.ts missing VERCEL_BLOB_READ_WRITE_TOKEN validation",
    body: `## Bug Report

\`apps/agents/lib/runs.ts\` uses \`@vercel/blob\` (put, list, get) which requires \`VERCEL_BLOB_READ_WRITE_TOKEN\` to be set. However, \`apps/agents/lib/env.ts\` doesn't validate this variable at startup.

When the token is missing, the app starts fine but crashes at runtime when trying to create or list runs — with a cryptic error from the blob SDK.

**Fix:** Add a \`blobToken()\` function to \`apps/agents/lib/env.ts\`:
\`\`\`ts
export function blobToken(): string {
  return required("VERCEL_BLOB_READ_WRITE_TOKEN");
}
\`\`\`

And call it during startup validation.

**Files:** \`apps/agents/lib/env.ts\`, \`apps/agents/lib/runs.ts\``,
    labels: ["bug"]
  },
  {
    title: "apps/agents GitHub webhook handler doesn't validate event type before casting",
    body: `## Bug Report

In \`apps/agents/app/api/github/route.ts\`, the POST handler casts the parsed body directly to \`GitHubIssuePayload\` without checking if the event is actually an issue event.

GitHub sends many webhook event types (push, PR, release, etc.) to the same endpoint. Non-issue events will have a completely different payload structure, causing runtime errors or silent failures.

**Fix:** Check the \`x-github-event\` header before processing:
\`\`\`ts
const event = request.headers.get("x-github-event");
if (event !== "issues") {
  return new Response("Ignored", { status: 200 });
}
\`\`\`

**File:** \`apps/agents/app/api/github/route.ts\`

**Impact:** Any non-issue webhook event can crash the handler or produce unexpected Slack messages.`,
    labels: ["bug"]
  },
  {
    title: "packages/turbo-codemod check-git-status swallows meaningful git errors",
    body: `## Bug Report

In \`packages/turbo-codemod/src/utils/check-git-status.ts\`, the catch block only checks for "not a git repository" but silently ignores all other git errors:

\`\`\`ts
} catch (err: unknown) {
  const errWithDetails = err as { stderr?: string };
  if (errWithDetails.stderr?.includes("not a git repository")) {
    clean = true;
  }
}
\`\`\`

If \`isGitClean.sync()\` throws for any other reason (corrupt git index, permission error, etc.), the error is swallowed and \`clean\` stays \`false\`, giving a misleading "Git directory is not clean" message.

**Fix:** Log the actual error in the else branch so users can diagnose:
\`\`\`ts
} else {
  errorMessage = errWithDetails.stderr || "Unknown git error";
}
\`\`\`

**File:** \`packages/turbo-codemod/src/utils/check-git-status.ts\``,
    labels: ["bug"]
  },
  {
    title: "docs API chat route uses expensive model for all queries — should use RAG model for retrieval",
    body: `## Performance

In \`apps/docs/app/api/chat/route.ts\`, two models are defined:

\`\`\`ts
const RAG_MODEL = "openai/gpt-4.1-mini";
const GENERATION_MODEL = "anthropic/claude-sonnet-4-20250514";
\`\`\`

But it's unclear from the code whether the RAG_MODEL is consistently used for the retrieval step. If the generation model is being used for retrieval as well, it's burning significantly more tokens and adding latency.

**Fix:** Audit the route handler to verify RAG_MODEL is passed to the retrieval tool calls and GENERATION_MODEL is only used for the final response generation. Add a comment clarifying which model is used where.

**File:** \`apps/docs/app/api/chat/route.ts\``,
    labels: ["enhancement"]
  },
  {
    title: "Add meta viewport tag to apps/agents layout for mobile responsiveness",
    body: `## Bug Report

\`apps/agents/app/layout.tsx\` renders \`<html>\` and \`<body>\` but doesn't include a viewport meta tag. This causes the dashboard to render at desktop scale on mobile devices.

**File:** \`apps/agents/app/layout.tsx\`

**Fix:** Next.js App Router supports the \`viewport\` export for this:
\`\`\`ts
export const viewport = {
  width: 'device-width',
  initialScale: 1,
};
\`\`\`

Or alternatively, add it via the metadata \`other\` field.

**Impact:** The agents dashboard is unusable on mobile — text is tiny and requires pinch-to-zoom.`,
    labels: ["bug"]
  },
  {
    title: "apps/agents reproduction request template has no link to docs on creating reproductions",
    body: `## Enhancement

In \`apps/agents/lib/templates.ts\`, the \`REPRODUCTION_REQUEST\` template tells users to provide a reproduction but doesn't link to any documentation on how to do it well.

**File:** \`apps/agents/lib/templates.ts\`

**Fix:** Add a link to the Turborepo contributing guide or a "How to create a minimal reproduction" guide. For example, add before the closing:

\`\`\`
For more guidance, see [How to create a minimal reproduction](https://turborepo.dev/docs/troubleshooting#reproduction).
\`\`\`

**Impact:** Users frequently submit issues without useful reproductions. A direct link would improve issue quality.`,
    labels: ["enhancement"]
  },
  {
    title: "apps/agents dashboard run list not sorted — newest runs should appear first",
    body: `## Bug Report

The dashboard page at \`apps/agents/app/dashboard/page.tsx\` fetches runs and displays them in whatever order the API returns. There's no sorting applied, so completed runs from days ago can appear above active runs.

**Expected:** Runs should be sorted by \`createdAt\` descending (newest first), with active runs (\`queued\`, \`scanning\`, \`fixing\`) pinned to the top.

**Fix:** Sort the \`runs\` array after fetching:
\`\`\`ts
const statusOrder = { scanning: 0, fixing: 0, queued: 1, completed: 2, failed: 2 };
runs.sort((a, b) => (statusOrder[a.status] ?? 2) - (statusOrder[b.status] ?? 2) || new Date(b.createdAt) - new Date(a.createdAt));
\`\`\`

**File:** \`apps/agents/app/dashboard/page.tsx\``,
    labels: ["bug"]
  }
];

async function seedIssues() {
  // First, close old seed issues
  console.log("Closing old seed issues...");
  const { data: existing } = await octokit.issues.listForRepo({
    owner, repo, state: 'open', per_page: 100
  });
  for (const issue of existing) {
    if (!issue.pull_request) {
      await octokit.issues.update({ owner, repo, issue_number: issue.number, state: 'closed' });
      console.log(`Closed #${issue.number}: ${issue.title}`);
      await new Promise(r => setTimeout(r, 300));
    }
  }

  console.log(`\nSeeding ${issues.length} real issues to ${owner}/${repo}...`);
  for (const issue of issues) {
    const res = await octokit.issues.create({ owner, repo, ...issue });
    console.log(`Created #${res.data.number}: ${issue.title}`);
    await new Promise(r => setTimeout(r, 800));
  }
  console.log("Done.");
}

seedIssues().catch(err => {
  console.error(err);
  process.exit(1);
});
