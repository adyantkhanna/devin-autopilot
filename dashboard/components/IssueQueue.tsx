'use client';

import { useState, useRef, useCallback } from 'react';
import IssueRow from './IssueRow';

export default function IssueQueue({
  issues, onSelectIssue, onRefresh, onReorderStart, onReorderEnd
}: {
  issues: any[];
  onSelectIssue: (issue: any) => void;
  onRefresh: () => void;
  onReorderStart?: () => void;
  onReorderEnd?: () => void;
}) {
  const [statusFilter, setStatusFilter] = useState('all');
  const [fixFilter, setFixFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);
  const [localOrder, setLocalOrder] = useState<any[] | null>(null);
  const dragNode = useRef<HTMLDivElement | null>(null);

  const displayList = localOrder || issues;

  const filtered = displayList.filter(i => {
    const status = i.dispatch_status || 'queued';
    if (statusFilter !== 'all' && status !== statusFilter) return false;
    if (fixFilter === 'auto' && !i.auto_fixable) return false;
    if (fixFilter === 'human' && i.auto_fixable) return false;
    if (riskFilter !== 'all' && i.risk_level !== riskFilter) return false;
    return true;
  });

  const isFiltering = statusFilter !== 'all' || fixFilter !== 'all' || riskFilter !== 'all';

  const handleDragStart = useCallback((e: React.DragEvent, idx: number) => {
    setDragIdx(idx);
    dragNode.current = e.currentTarget as HTMLDivElement;
    e.dataTransfer.effectAllowed = 'move';
    onReorderStart?.();
    requestAnimationFrame(() => {
      if (dragNode.current) dragNode.current.style.opacity = '0.4';
    });
  }, [onReorderStart]);

  const handleDragEnd = useCallback(() => {
    if (dragNode.current) dragNode.current.style.opacity = '1';
    setDragIdx(null);
    setOverIdx(null);
    dragNode.current = null;
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, idx: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setOverIdx(idx);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent, dropIdx: number) => {
    e.preventDefault();
    if (dragIdx === null || dragIdx === dropIdx) {
      handleDragEnd();
      onReorderEnd?.();
      return;
    }

    const source = localOrder || issues;
    const newList = [...source];
    const [moved] = newList.splice(dragIdx, 1);
    newList.splice(dropIdx, 0, moved);
    setLocalOrder(newList);

    // Reset drag visuals
    if (dragNode.current) dragNode.current.style.opacity = '1';
    setDragIdx(null);
    setOverIdx(null);
    dragNode.current = null;

    // Persist to backend
    const order = newList.map(i => i.github_number);
    try {
      await fetch('/api/issues/reorder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order }),
      });
      // Refresh parent data, then clear local override
      await onRefresh();
    } catch (err) {
      console.error('Reorder failed', err);
    }
    // Small delay to let the refreshed data arrive before clearing local state
    setTimeout(() => {
      setLocalOrder(null);
      onReorderEnd?.();
    }, 2000);
  }, [dragIdx, issues, localOrder, onRefresh, onReorderEnd, handleDragEnd]);

  return (
    <div className="panel">
      <h2>Issue Queue</h2>
      <div className="filter-bar">
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All statuses</option>
          <option value="queued">Queued</option>
          <option value="in_progress">In progress</option>
          <option value="pr_open">PR open</option>
          <option value="done">Done</option>
          <option value="failed">Failed</option>
        </select>
        <select value={fixFilter} onChange={e => setFixFilter(e.target.value)}>
          <option value="all">All fixability</option>
          <option value="auto">Auto-fixable</option>
          <option value="human">Needs human</option>
        </select>
        <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)}>
          <option value="all">All risk</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>
      {filtered.length === 0 && (
        <div className="empty-state">No issues match current filters.</div>
      )}
      {filtered.map((issue, idx) => (
        <div
          key={issue.github_number}
          draggable={!isFiltering}
          onDragStart={e => handleDragStart(e, idx)}
          onDragEnd={handleDragEnd}
          onDragOver={e => handleDragOver(e, idx)}
          onDrop={e => handleDrop(e, idx)}
          className={`drag-wrapper${overIdx === idx && dragIdx !== idx ? ' drag-over' : ''}${dragIdx === idx ? ' dragging' : ''}`}
        >
          <IssueRow
            issue={issue}
            rank={idx + 1}
            onClick={() => onSelectIssue(issue)}
            onAction={onRefresh}
          />
        </div>
      ))}
    </div>
  );
}
