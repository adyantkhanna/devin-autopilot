'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import TopBar from '../components/TopBar';
import StatsRow from '../components/StatsRow';
import IssueQueue from '../components/IssueQueue';
import ActivityFeed from '../components/ActivityFeed';
import IssueDrawer from '../components/IssueDrawer';
import { Issue, Stats, ActivityEvent } from '../types';

const AUTO_REFRESH_MS = 30_000;
const DRAWER_REFRESH_MS = 15_000;

export default function DashboardPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [mode, setMode] = useState<'supervised' | 'autopilot'>('supervised');
  const [period, setPeriod] = useState('7d');
  const [lastSync, setLastSync] = useState<Date>(new Date());
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const reorderingRef = useRef(false);
  const periodRef = useRef(period);
  periodRef.current = period;

  const load = useCallback(async () => {
    if (reorderingRef.current) return;
    try {
      const [i, s, a, c] = await Promise.all([
        fetch('/api/issues').then(r => r.json()),
        fetch(`/api/stats?period=${periodRef.current}`).then(r => r.json()),
        fetch('/api/activity').then(r => r.json()),
        fetch('/api/config').then(r => r.json())
      ]);
      if (!reorderingRef.current) {
        setIssues(Array.isArray(i) ? i : []);
      }
      setStats(s || null);
      setActivity(Array.isArray(a) ? a : []);
      setMode((c?.mode as 'supervised' | 'autopilot') || 'supervised');
      setLastSync(new Date());
    } catch (err) {
      console.error('Failed to load data', err);
    }
  }, []);

  // Refresh faster (10s) when issues are in-progress, otherwise 30s
  const hasInProgress = issues.some(i => i.dispatch_status === 'in_progress');
  const refreshIntervalRef = useRef(AUTO_REFRESH_MS);
  refreshIntervalRef.current = hasInProgress ? 10_000 : AUTO_REFRESH_MS;

  useEffect(() => {
    load();
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      timer = setTimeout(() => {
        load();
        tick();
      }, refreshIntervalRef.current);
    };
    tick();
    return () => clearTimeout(timer);
  }, [load]);

  const handlePeriodChange = (p: string) => {
    setPeriod(p);
    periodRef.current = p;
    // Fetch stats immediately with new period
    fetch(`/api/stats?period=${p}`).then(r => r.json()).then(s => setStats(s || null));
  };

  const handleModeToggle = async (newMode: 'supervised' | 'autopilot') => {
    await fetch('/api/config/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: newMode })
    });
    setMode(newMode);
    load();
  };

  return (
    <>
      <TopBar
        mode={mode}
        onModeChange={handleModeToggle}
        lastSync={lastSync}
        onRefresh={load}
      />
      <StatsRow stats={stats} period={period} onPeriodChange={handlePeriodChange} />
      <div className="main-grid">
        <IssueQueue
          issues={issues}
          onSelectIssue={setSelectedIssue}
          onRefresh={load}
          onReorderStart={() => { reorderingRef.current = true; }}
          onReorderEnd={() => { reorderingRef.current = false; }}
        />
        <ActivityFeed events={activity} />
      </div>
      {selectedIssue && (
        <IssueDrawer
          issue={selectedIssue}
          onClose={() => setSelectedIssue(null)}
          onAction={load}
        />
      )}
    </>
  );
}
