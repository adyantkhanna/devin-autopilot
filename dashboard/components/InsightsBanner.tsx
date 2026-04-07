'use client';

export default function InsightsBanner({ issues, stats }: { issues: any[]; stats: any }) {
  const insights: { icon: string; text: string; type: 'info' | 'warning' | 'success' }[] = [];

  // Success: closed issues
  const closed = stats.closed || 0;
  if (closed > 0) {
    const hours = closed * 3;
    insights.push({
      icon: '🎯',
      text: `Devin resolved ${closed} issue${closed > 1 ? 's' : ''} this week — saving your team ~${hours} engineering hours`,
      type: 'success'
    });
  }

  // Warning: PRs awaiting review
  const prsOpen = issues.filter(i => i.dispatch_status === 'pr_open');
  if (prsOpen.length > 0) {
    insights.push({
      icon: '👀',
      text: `${prsOpen.length} PR${prsOpen.length > 1 ? 's' : ''} awaiting review — merge to close the loop`,
      type: 'warning'
    });
  }

  // Info: stale issues
  const now = Date.now();
  const stale = issues.filter(i => {
    if (!i.created_at) return false;
    const age = (now - new Date(i.created_at).getTime()) / (1000 * 60 * 60 * 24);
    return age > 14 && (!i.dispatch_status || i.dispatch_status === 'queued');
  });
  if (stale.length > 0) {
    insights.push({
      icon: '⏰',
      text: `${stale.length} issue${stale.length > 1 ? 's have' : ' has'} been open 14+ days without action`,
      type: 'info'
    });
  }

  // Info: auto-fixable ready
  const ready = issues.filter(i => i.auto_fixable && (!i.dispatch_status || i.dispatch_status === 'queued'));
  const inProgress = issues.filter(i => i.dispatch_status === 'in_progress');
  if (ready.length > 0 && inProgress.length === 0) {
    insights.push({
      icon: '🚀',
      text: `${ready.length} issue${ready.length > 1 ? 's are' : ' is'} ready to dispatch — Devin can start fixing now`,
      type: 'info'
    });
  }

  // In progress update
  if (inProgress.length > 0) {
    insights.push({
      icon: '⚡',
      text: `Devin is actively working on ${inProgress.length} issue${inProgress.length > 1 ? 's' : ''} right now`,
      type: 'info'
    });
  }

  // Needs human attention
  const needsHuman = issues.filter(i => !i.auto_fixable && (!i.dispatch_status || i.dispatch_status === 'queued'));
  if (needsHuman.length > 0) {
    insights.push({
      icon: '🔶',
      text: `${needsHuman.length} issue${needsHuman.length > 1 ? 's need' : ' needs'} human guidance before Devin can fix`,
      type: 'warning'
    });
  }

  if (insights.length === 0) return null;

  // Show max 3 insights
  const visible = insights.slice(0, 3);

  const colors = {
    info: { bg: '#161620', border: '#1e1e2e', text: '#8888cc' },
    warning: { bg: '#1a1810', border: '#2e2a1a', text: '#d4a843' },
    success: { bg: '#141a14', border: '#1a2e1a', text: '#6fcf6f' },
  };

  return (
    <div style={{ padding: '0 28px', display: 'flex', gap: 10 }}>
      {visible.map((insight, idx) => {
        const c = colors[insight.type];
        return (
          <div
            key={idx}
            style={{
              flex: 1,
              background: c.bg,
              border: `1px solid ${c.border}`,
              borderRadius: 10,
              padding: '12px 16px',
              fontSize: 12,
              color: c.text,
              lineHeight: 1.5,
            }}
          >
            <span style={{ marginRight: 6 }}>{insight.icon}</span>
            {insight.text}
          </div>
        );
      })}
    </div>
  );
}
