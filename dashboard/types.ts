export interface Issue {
  id: number;
  github_number: number;
  title: string;
  body: string | null;
  labels: string;
  state: string;
  created_at: string;
  updated_at: string;
  triage_status: string;
  fixability_score: number | null;
  impact_score: number | null;
  staleness_score: number | null;
  complexity_score: number | null;
  priority_score: number | null;
  affected_files: string | null;
  triage_summary: string | null;
  risk_level: string | null;
  auto_fixable: number;
  devin_instructions: string | null;
  needs_human_reason: string | null;
  manual_priority_order: number | null;
  override_by: string | null;
  override_at: string | null;
  dispatch_status: string;
  devin_session_id: string | null;
  devin_session_url: string | null;
  pr_url: string | null;
  pr_number: number | null;
  failure_reason: string | null;
  dispatched_at: string | null;
  completed_at: string | null;
  activity?: ActivityEvent[];
}

export interface ActivityEvent {
  id: number;
  github_number: number;
  event_type: string;
  message: string;
  triggered_by: string;
  created_at: string;
}

export interface Stats {
  total_open: number;
  devin_ready: number;
  in_progress: number;
  prs_open: number;
  closed: number;
  dispatched: number;
  failed: number;
  oldest_pr_hours: number | null;
  period: string;
  period_label: string;
}

export type DispatchStatus = 'queued' | 'in_progress' | 'pr_open' | 'done' | 'failed' | 'paused';
export type RiskLevel = 'low' | 'medium' | 'high';
export type FilterTab = 'all' | 'queued' | 'in_progress' | 'pr_open' | 'done' | 'failed';
