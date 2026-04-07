'use client';

import { Stats } from '../types';

export default function StatsRow({
  stats, period, onPeriodChange
}: {
  stats: Stats | null;
  period: string;
  onPeriodChange: (p: string) => void;
}) {
  const hoursSaved = (stats?.closed || 0) * 3;
  const periodLabel = stats?.period_label || 'this week';

  const cards = [
    { label: 'Open issues', value: stats?.total_open, sub: null },
    { label: 'Devin ready', value: stats?.devin_ready, sub: 'auto-fixable' },
    { label: 'In progress', value: stats?.in_progress, sub: 'right now' },
    { label: 'PRs open', value: stats?.prs_open, sub: 'awaiting review' },
    { label: 'Dispatched', value: stats?.dispatched, sub: periodLabel },
    { label: 'Closed', value: stats?.closed, sub: hoursSaved ? `~${hoursSaved}h saved` : periodLabel },
  ];

  return (
    <div style={{ padding: '22px 28px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ color: '#777', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Overview
        </div>
        <select
          className="period-select"
          value={period}
          onChange={e => onPeriodChange(e.target.value)}
        >
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="all">All time</option>
        </select>
      </div>
      <div className="stats-row">
        {cards.map(c => (
          <div className="stat-card" key={c.label}>
            <div className="label">{c.label}</div>
            <div className="value">{c.value ?? '—'}</div>
            {c.sub && <div className="sub">{c.sub}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
