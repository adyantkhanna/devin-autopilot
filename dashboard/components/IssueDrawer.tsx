'use client';

import { useEffect, useState } from 'react';
import { Issue, ActivityEvent } from '../types';

export default function IssueDrawer({
  issue, onClose, onAction
}: {
  issue: Issue;
  onClose: () => void;
  onAction: () => void;
}) {
  const [detail, setDetail] = useState<Issue>(issue);
  const [instructions, setInstructions] = useState('');
  const [dispatching, setDispatching] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`/api/issues/${issue.github_number}`);
        const data = await res.json();
        if (alive) setDetail(data);
      } catch (err) { console.error('Failed to fetch issue detail', err); }
    };
    load();
    // Refresh drawer detail periodically (every 15s)
    const interval = setInterval(load, 15000);
    return () => { alive = false; clearInterval(interval); };
  }, [issue.github_number]);

  const affectedFiles: string[] = (() => {
    try { return JSON.parse(detail.affected_files || '[]'); }
    catch (err) { console.error('Failed to parse affected_files', err); return []; }
  })();

  const act = async (path: string, body?: object) => {
    await fetch(`/api/issues/${issue.github_number}/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    onAction();
  };

  const reloadDetail = async () => {
    try {
      const res = await fetch(`/api/issues/${issue.github_number}`);
      const data = await res.json();
      setDetail(data);
    } catch (err) { console.error('Failed to reload issue detail', err); }
  };

  const handleDispatch = async () => {
    setDispatching(true);
    try {
      await fetch(`/api/issues/${issue.github_number}/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          triggered_by: 'dashboard',
          human_instructions: instructions || undefined,
        }),
      });
      setInstructions('');
      // Backend has updated DB to in_progress — reload detail immediately
      await reloadDetail();
      onAction();
      // Keep polling to catch further status changes
      setTimeout(() => { reloadDetail(); onAction(); }, 3000);
      setTimeout(() => { reloadDetail(); onAction(); }, 8000);
    } catch (err) {
      console.error('Failed to dispatch issue', err);
      setDispatching(false);
    }
    // Don't setDispatching(false) — reloadDetail will update detail.dispatch_status
    // which changes what the UI renders (from dispatch button to "In progress" tag)
  };

  const riskColor = { low: '#6fcf6f', medium: '#d4a843', high: '#cf6f6f' }[detail.risk_level as string] || '#777';
  const canDispatch = !dispatching && (!detail.dispatch_status || detail.dispatch_status === 'queued' || detail.dispatch_status === 'failed');

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <button className="close-btn" onClick={onClose} aria-label="Close drawer">×</button>

        <div style={{ marginBottom: 20 }}>
          <span style={{ color: '#555', fontSize: 12, fontWeight: 500 }}>Issue #{detail.github_number}</span>
          <h2 style={{ marginTop: 4 }}>{detail.title}</h2>
        </div>

        <div style={{ color: '#999', fontSize: 12, lineHeight: 1.6, marginBottom: 20 }}>
          {detail.triage_summary}
        </div>

        <div className="score-grid">
          <div>
            <div className="label">Fixability</div>
            <div className="val">{detail.fixability_score ?? '—'}<span style={{ fontSize: 12, color: '#555', fontWeight: 400 }}>/10</span></div>
          </div>
          <div>
            <div className="label">Impact</div>
            <div className="val">{detail.impact_score ?? '—'}<span style={{ fontSize: 12, color: '#555', fontWeight: 400 }}>/10</span></div>
          </div>
          <div>
            <div className="label">Complexity</div>
            <div className="val">{detail.complexity_score ?? '—'}<span style={{ fontSize: 12, color: '#555', fontWeight: 400 }}>/10</span></div>
          </div>
          <div>
            <div className="label">Priority score</div>
            <div className="val">{detail.priority_score?.toFixed?.(1) ?? '—'}</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 20, margin: '16px 0 20px' }}>
          <div>
            <div className="drawer-label">Risk</div>
            <div style={{ color: riskColor, fontSize: 13, fontWeight: 600, marginTop: 4 }}>{detail.risk_level || '—'}</div>
          </div>
          <div>
            <div className="drawer-label">Auto-fixable</div>
            <div style={{ color: detail.auto_fixable ? '#6fcf6f' : '#cf6f6f', fontSize: 13, fontWeight: 600, marginTop: 4 }}>
              {detail.auto_fixable ? 'Yes' : 'No'}
            </div>
          </div>
          {detail.completed_at && (
            <div>
              <div className="drawer-label">Completed</div>
              <div style={{ color: '#6fcf6f', fontSize: 13, fontWeight: 600, marginTop: 4 }}>
                {new Date(detail.completed_at + (detail.completed_at.endsWith('Z') ? '' : 'Z')).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </div>
            </div>
          )}
          {detail.dispatched_at && !detail.completed_at && (
            <div>
              <div className="drawer-label">Dispatched</div>
              <div style={{ color: '#d4a843', fontSize: 13, fontWeight: 600, marginTop: 4 }}>
                {new Date(detail.dispatched_at + (detail.dispatched_at.endsWith('Z') ? '' : 'Z')).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </div>
            </div>
          )}
        </div>

        {affectedFiles.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div className="drawer-label" style={{ marginBottom: 6 }}>Affected files</div>
            {affectedFiles.map(f => (
              <div key={f} style={{ fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: 11, color: '#888', padding: '3px 0' }}>{f}</div>
            ))}
          </div>
        )}

        {detail.devin_instructions && (
          <div style={{ marginBottom: 16 }}>
            <div className="drawer-label" style={{ marginBottom: 6 }}>AI-generated instructions</div>
            <div className="drawer-code-block">
              {detail.devin_instructions}
            </div>
          </div>
        )}

        {detail.needs_human_reason && (
          <div style={{ marginBottom: 16 }}>
            <div className="drawer-label" style={{ marginBottom: 6 }}>Why this needs a human</div>
            <div className="drawer-warning-block">
              {detail.needs_human_reason}
            </div>
          </div>
        )}

        {/* ---- Human Instructions Input ---- */}
        {canDispatch && (
          <div className="instructions-section">
            <div className="drawer-label" style={{ marginBottom: 6 }}>
              {detail.auto_fixable ? 'Additional instructions (optional)' : 'Provide instructions for Devin'}
            </div>
            <textarea
              className="instructions-input"
              placeholder={
                detail.auto_fixable
                  ? 'Add any extra context or constraints for Devin...'
                  : 'This issue needs human guidance. Tell Devin exactly what to do — approach, constraints, files to focus on...'
              }
              value={instructions}
              onChange={e => setInstructions(e.target.value)}
              rows={4}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button
                className="btn-primary"
                onClick={handleDispatch}
                disabled={dispatching || (!detail.auto_fixable && !instructions.trim())}
                style={(!detail.auto_fixable && !instructions.trim()) ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
              >
                {dispatching ? 'Dispatching…' : (
                  detail.auto_fixable
                    ? (instructions.trim() ? 'Dispatch with instructions' : 'Dispatch to Devin')
                    : 'Dispatch with instructions'
                )}
              </button>
              <button className="btn-secondary" onClick={() => act('prioritize')}>Move to top</button>
            </div>
            {!detail.auto_fixable && !instructions.trim() && (
              <div style={{ fontSize: 11, color: '#777', marginTop: 6 }}>
                Instructions are required for issues that need human guidance.
              </div>
            )}
          </div>
        )}

        {/* ---- In-progress / completed actions ---- */}
        {detail.dispatch_status === 'in_progress' && (
          <div style={{ display: 'flex', gap: 8, marginTop: 24, paddingTop: 16, borderTop: '1px solid #1e1e1e' }}>
            <button className="btn-secondary" onClick={() => act('pause')}>Pause session</button>
            {detail.devin_session_url && (
              <a href={detail.devin_session_url} target="_blank" rel="noopener noreferrer">
                <button className="btn-secondary">View in Devin →</button>
              </a>
            )}
          </div>
        )}

        {detail.pr_url && (
          <div style={{ marginTop: detail.dispatch_status === 'in_progress' ? 8 : 24, paddingTop: detail.dispatch_status === 'in_progress' ? 0 : 16, borderTop: detail.dispatch_status === 'in_progress' ? 'none' : '1px solid #1e1e1e' }}>
            <a href={detail.pr_url} target="_blank" rel="noopener noreferrer">
              <button className="btn-primary" style={{ background: '#1a2e1a', color: '#6fcf6f' }}>View Pull Request →</button>
            </a>
          </div>
        )}

        {detail.activity && detail.activity.length > 0 && (
          <div style={{ marginTop: 24, borderTop: '1px solid #1e1e1e', paddingTop: 16 }}>
            <div className="drawer-label" style={{ marginBottom: 14 }}>Session log</div>
            <div style={{ position: 'relative', paddingLeft: 24 }}>
              {/* Timeline line */}
              <div style={{ position: 'absolute', left: 7, top: 6, bottom: 6, width: 1, background: '#2a2a2a' }} />
              {[...detail.activity].reverse().map((ev: ActivityEvent, idx: number) => {
                const iconMap: Record<string, string> = {
                  triaged: '🔍',
                  dispatched: '🚀',
                  human_instructions: '📝',
                  pr_opened: '✅',
                  completed: '🎉',
                  failed: '⚠️',
                  paused: '⏸️',
                  prioritized: '📌',
                };
                const colorMap: Record<string, string> = {
                  triaged: '#8888cc',
                  dispatched: '#d4a843',
                  human_instructions: '#8888cc',
                  pr_opened: '#6fcf6f',
                  completed: '#6fcf6f',
                  failed: '#cf6f6f',
                  paused: '#d4a843',
                  prioritized: '#d4a843',
                };
                const icon = iconMap[ev.event_type] || '•';
                const color = colorMap[ev.event_type] || '#555';
                const time = ev.created_at
                  ? new Date(ev.created_at + (ev.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString('en-US', {
                      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true
                    })
                  : '';
                return (
                  <div key={ev.id || idx} style={{ position: 'relative', paddingBottom: idx < detail.activity.length - 1 ? 16 : 0 }}>
                    {/* Timeline dot */}
                    <div style={{
                      position: 'absolute', left: -20, top: 2, width: 15, height: 15,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10,
                      zIndex: 1,
                    }}>
                      {icon}
                    </div>
                    <div style={{ fontSize: 10, color: '#555', marginBottom: 2, fontVariantNumeric: 'tabular-nums' }}>
                      {time}
                      {ev.triggered_by && ev.triggered_by !== 'system' && (
                        <span style={{ marginLeft: 6, color: '#444' }}>via {ev.triggered_by}</span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color, lineHeight: 1.5 }}>
                      {ev.message}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
