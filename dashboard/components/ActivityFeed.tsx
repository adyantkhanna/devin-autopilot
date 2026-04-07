'use client';

function timeAgo(ts: string) {
  const d = new Date(ts + (ts.endsWith('Z') ? '' : 'Z'));
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function dotColor(eventType: string) {
  if (['pr_opened', 'completed'].includes(eventType)) return 'green';
  if (['dispatched', 'triaged'].includes(eventType)) return 'blue';
  if (['failed'].includes(eventType)) return 'red';
  return 'gray';
}

export default function ActivityFeed({ events }: { events: any[] }) {
  return (
    <div className="panel">
      <h2>Activity</h2>
      {events.length === 0 && (
        <div className="empty-state">No activity yet.</div>
      )}
      {events.map(ev => (
        <div key={ev.id} className="activity-item">
          <div className={`activity-dot ${dotColor(ev.event_type)}`} />
          <div style={{ minWidth: 0 }}>
            <div className="text">{ev.message}</div>
            <div className="time">{timeAgo(ev.created_at)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
