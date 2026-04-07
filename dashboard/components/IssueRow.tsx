'use client';

import { useState } from 'react';
import { Issue } from '../types';

export default function IssueRow({
  issue, rank, onClick, onAction
}: {
  issue: Issue;
  rank: number;
  onClick: () => void;
  onAction: () => void;
}) {
  const [dispatching, setDispatching] = useState(false);

  const status = dispatching ? 'in_progress' : (issue.dispatch_status || 'queued');
  const statusLabel = {
    queued: issue.auto_fixable ? 'Ready' : 'Manual',
    in_progress: 'In progress',
    pr_open: 'PR open',
    done: 'Done',
    failed: 'Failed',
    paused: 'Paused'
  }[status] || status;

  const statusDotColor: Record<string, string> = {
    queued: issue.auto_fixable ? '#c4f441' : '#555',
    in_progress: '#d4a843',
    pr_open: '#6fcf6f',
    done: '#6fcf6f',
    failed: '#cf6f6f',
    paused: '#555'
  };

  const actionBtn = () => {
    if (!issue.auto_fixable) {
      return <span className="row-tag row-tag-manual">Manual</span>;
    }
    if (dispatching) {
      return <span className="row-tag row-tag-progress">Dispatching…</span>;
    }
    if (issue.dispatch_status === 'queued' || !issue.dispatch_status) {
      return (
        <button
          className="btn-primary btn-sm"
          onClick={async (e) => {
            e.stopPropagation();
            setDispatching(true);
            try {
              await fetch(`/api/issues/${issue.github_number}/dispatch`, { method: 'POST' });
            } catch (err) { console.error('Failed to dispatch issue', err); }
            // Refresh multiple times to catch backend status update
            onAction();
            setTimeout(onAction, 1500);
            setTimeout(onAction, 3000);
            setTimeout(onAction, 5000);
          }}
        >
          Dispatch
        </button>
      );
    }
    if (issue.dispatch_status === 'in_progress') {
      return <span className="row-tag row-tag-progress">In progress</span>;
    }
    if (issue.dispatch_status === 'pr_open') {
      return (
        <a href={issue.pr_url || '#'} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
          <span className="row-tag row-tag-pr">PR open</span>
        </a>
      );
    }
    if (issue.dispatch_status === 'done') {
      return <span className="row-tag row-tag-done">Done</span>;
    }
    return null;
  };

  return (
    <div className={`issue-row${status === 'done' || status === 'failed' ? ' issue-row-dimmed' : ''}`} onClick={onClick} role="button" tabIndex={0}>
      <span className="drag-handle" title="Drag to reorder">⠿</span>
      <span className="rank">{rank}</span>
      <div className="content">
        <div className="title">
          <span className="issue-num">#{issue.github_number}</span>
          {issue.title}
        </div>
        <div className="summary">{issue.triage_summary || 'Awaiting triage…'}</div>
      </div>
      <div className="row-meta" />
      {actionBtn()}
    </div>
  );
}
