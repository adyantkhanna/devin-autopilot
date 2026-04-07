'use client';

export default function TopBar({
  mode, onModeChange, lastSync, onRefresh
}: {
  mode: 'supervised' | 'autopilot';
  onModeChange: (m: 'supervised' | 'autopilot') => void;
  lastSync: Date;
  onRefresh: () => void;
}) {
  const repoUrl = `https://github.com/${process.env.NEXT_PUBLIC_GITHUB_OWNER || 'your-org'}/finserv-monorepo`;
  return (
    <div className="top-bar">
      <h1>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#c4f441" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4l3 3" />
        </svg>
        Devin Autopilot
        <span style={{ color: '#444', fontWeight: 400, fontSize: 13 }}>·</span>
        <a href={repoUrl} target="_blank" rel="noopener noreferrer">finserv-monorepo</a>
      </h1>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div className="mode-toggle">
          <button
            className={mode === 'supervised' ? 'active' : ''}
            onClick={() => onModeChange('supervised')}
          >
            Supervised
          </button>
          <button
            className={mode === 'autopilot' ? 'active' : ''}
            onClick={() => onModeChange('autopilot')}
          >
            Autopilot
          </button>
        </div>
        <span style={{ fontSize: 11, color: '#555', fontVariantNumeric: 'tabular-nums' }}>
          {lastSync.toLocaleTimeString()}
        </span>
        <button className="btn-secondary" onClick={onRefresh} style={{ padding: '5px 10px', fontSize: 14 }}>
          ↻
        </button>
      </div>
    </div>
  );
}
