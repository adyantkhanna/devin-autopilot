// seed-issues.js — creates realistic demo issues in your finserv-monorepo fork
// Usage:
//   npm install @octokit/rest
//   GITHUB_TOKEN=xxx GITHUB_OWNER=your-username node seed-issues.js

import { Octokit } from '@octokit/rest';

const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
const owner = process.env.GITHUB_OWNER;
const repo = 'finserv-monorepo';

const issues = [
  {
    title: 'Turbo cache not working for test tasks',
    body: `## Bug Report\n\nRunning \`turbo run test\` never uses cache — every run re-executes all tests even when nothing has changed.\n\n**Root cause (suspected):** The \`outputs\` field is missing from the \`test\` pipeline config in \`turbo.json\`.\n\n**Fix:** Add \`"outputs": ["coverage/**"]\` to the test pipeline entry.\n\n**Impact:** CI is 3x slower than it needs to be.`,
    labels: ['bug', 'stale']
  },
  {
    title: 'ESLint errors in packages/config blocking CI',
    body: `## Bug Report\n\nCI is failing on the lint step due to unused variable errors in \`packages/config/index.js\`.\n\n\`\`\`\nno-unused-vars: 'defaultTimeout' is defined but never used\nno-unused-vars: 'retryCount' is defined but never used\n\`\`\`\n\nThese were leftover from a refactor 3 months ago. Safe to remove.`,
    labels: ['bug', 'stale']
  },
  {
    title: 'Fix broken pagination in /api/users endpoint',
    body: `## Bug Report\n\n\`GET /api/users?page=2\` always returns the first page regardless of the page param.\n\n**File:** \`apps/api/routes/users.ts\`\n\n**Root cause:** The offset calculation uses \`page\` directly but should use \`(page - 1) * pageSize\`. Pages are 1-indexed in the UI but the query treats them as 0-indexed.`,
    labels: ['bug', 'stale']
  },
  {
    title: 'Missing error boundary in apps/web causes full page crash',
    body: `## Bug Report\n\nIf any child component throws an unhandled error, the entire app unmounts with a blank white screen. No error message shown to user.\n\n**Fix:** Wrap the root layout in \`apps/web/app/layout.tsx\` with a React Error Boundary that shows a user-friendly fallback UI with a retry button.`,
    labels: ['bug', 'stale']
  },
  {
    title: 'TypeScript strict mode errors in shared/ui package',
    body: `## Bug Report\n\nAfter upgrading TypeScript to 5.x, the shared/ui package throws 12 strict mode errors blocking the build.\n\n**Examples:**\n\`\`\`\nArgument of type 'string | undefined' is not assignable to parameter of type 'string'\n\`\`\`\n\n**Files:** \`packages/ui/src/Button.tsx\`, \`packages/ui/src/Input.tsx\`\n\n**Fix:** Add proper null checks or update type signatures to handle undefined.`,
    labels: ['bug', 'typescript', 'stale']
  },
  {
    title: 'Add loading skeleton to user profile page',
    body: `## Feature Request\n\nThe user profile page at \`/profile\` shows a blank white screen while data loads. We need a skeleton loader matching the layout of the profile card.\n\n**Reference:** We already have a \`Skeleton\` component in \`packages/ui/src/Skeleton.tsx\` — just needs to be wired up in \`apps/web/app/profile/page.tsx\`.`,
    labels: ['enhancement', 'stale']
  },
  {
    title: 'API fetch fails silently in apps/web dashboard page',
    body: `## Bug Report\n\nThe dashboard page at \`/dashboard\` makes a fetch call to \`/api/metrics\` that fails with a 401 but shows no error to the user — the page just stays in a loading state forever.\n\n**Root cause (suspected):** Missing auth header in \`apps/web/lib/api.ts\`.\n\n**Expected behavior:** Show error state with retry button when API call fails.`,
    labels: ['bug', 'stale']
  },
  {
    title: 'Mobile navbar overlaps page content on small screens',
    body: `## Bug Report\n\nOn screens under 768px, the top navbar overlaps the main content area by ~60px, making the first section unreadable.\n\n**Steps to reproduce:**\n1. Open the app on mobile or resize browser to <768px\n2. Content is hidden behind the navbar\n\n**Expected:** Content should have correct top padding to offset the fixed navbar height.\n\n**Affected file:** \`apps/web/components/Navbar.tsx\``,
    labels: ['bug', 'stale']
  },
  {
    title: 'Add dark mode toggle to app header',
    body: `## Feature Request\n\nUsers have requested a dark mode toggle. We already have a \`ThemeContext\` set up in \`apps/web/context/ThemeContext.tsx\` but there's no UI control exposed in the header.\n\n**Requirements:**\n- Sun/moon icon button in the header\n- Toggle persists to localStorage\n- Respects system preference on first load`,
    labels: ['enhancement', 'stale']
  },
  {
    title: 'Add input validation to contact form',
    body: `## Feature Request\n\nThe contact form at \`/contact\` submits with empty fields and no client-side validation.\n\n**Required:**\n- Required field checks on name, email, message\n- Email format validation\n- Inline error messages below each field\n\nWe're using React Hook Form elsewhere in the app — use the same pattern from \`apps/web/app/login/page.tsx\`.`,
    labels: ['enhancement', 'stale']
  },
  {
    title: 'Upgrade deprecated React Router v5 patterns in apps/web',
    body: `## Technical Debt\n\nSeveral components still use deprecated React Router v5 patterns that will break in the next major upgrade.\n\n**Affected patterns:**\n- \`useHistory\` → replace with \`useNavigate\`\n- \`<Redirect>\` → replace with \`<Navigate>\`\n\n**Files:** 6 components in \`apps/web/components/\``,
    labels: ['technical-debt', 'stale']
  },
  {
    title: 'Environment variable validation missing at startup',
    body: `## Bug Report\n\nThe app starts without validating required environment variables. When a variable is missing, the app crashes at runtime with a cryptic error instead of a clear startup message.\n\n**Fix:** Add a startup validation script using \`zod\` (already installed) that checks all required env vars and exits with a clear error message if any are missing.\n\n**File:** Create \`apps/web/lib/env.ts\``,
    labels: ['bug', 'stale']
  }
];

const labelDefs = [
  { name: 'devin-ready', color: '22c55e', description: 'Triaged, auto-fixable, ready to dispatch' },
  { name: 'needs-human', color: 'ef4444', description: 'Too complex or risky for Devin' },
  { name: 'dispatch-devin', color: '3b82f6', description: 'Manually triggered dispatch' },
  { name: 'devin-in-progress', color: 'eab308', description: 'Devin actively working' },
  { name: 'devin-done', color: 'a855f7', description: 'Devin opened a PR' },
  { name: 'stale', color: '9ca3af', description: 'Issue untouched for 30+ days' }
];

async function ensureLabels() {
  for (const label of labelDefs) {
    try {
      await octokit.issues.createLabel({ owner, repo, ...label });
      console.log(`Created label: ${label.name}`);
    } catch (err) {
      if (err.status === 422) {
        console.log(`Label exists: ${label.name}`);
      } else {
        throw err;
      }
    }
  }
}

async function seedIssues() {
  console.log(`Seeding ${issues.length} issues to ${owner}/${repo}...`);
  await ensureLabels();
  for (const issue of issues) {
    const res = await octokit.issues.create({ owner, repo, ...issue });
    console.log(`Created #${res.data.number}: ${issue.title}`);
    await new Promise(r => setTimeout(r, 800));
  }
  console.log('Done.');
}

seedIssues().catch(err => {
  console.error(err);
  process.exit(1);
});
