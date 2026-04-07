'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import TopBar from '../components/TopBar';
import StatsRow from '../components/StatsRow';
import IssueQueue from '../components/IssueQueue';
import ActivityFeed from '../components/ActivityFeed';
import IssueDrawer from '../components/IssueDrawer';

export default function DashboardPage() {
  const [issues, setIssues] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({});
  const [activity, setActivity] = useState<any[]>([]);
  const [mode, setMode] = useState<'supervised' | 'autopilot'>('supervised');
  const [period, setPeriod] = useState('7d');
  const [lastSync, setLastSync] = useState<Date>(new Date());
  const [selectedIssue, setSelectedIssue] = useState<any>(null);
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
      setStats(s || {});
      setActivity(Array.isArray(a) ? a : []);
      setMode((c?.mode as any) || 'supervised');
      setLastSync(new Date());
    } catch (err) {
      console.error('Failed to load data', err);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  const handlePeriodChange = (p: string) => {
    setPeriod(p);
    periodRef.current = p;
    // Fetch stats immediately with new period
    fetch(`/api/stats?period=${p}`).then(r => r.json()).then(s => setStats(s || {}));
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
