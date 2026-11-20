import { API_BASE } from './apiClient';
import type { ClipJob } from '../types/clip.type';

export type FacebookSession = {
  status?: string; logged_in?: boolean | null; account_verified?: boolean;
  message?: string; checked_at?: string; target_email?: string;
  professional_mode?: boolean | null;
};
export type FacebookConfig = {
  version: number; target_email: string; target_seconds: number; max_seconds: number;
  shared_browser: boolean; session: FacebookSession; login_note: string;
  niches: {key: string; label: string; brief: string; queries: string[]}[];
};
export type FacebookProduction = {job: ClipJob; results: {clip_url: string; caption: string}[]};
export type FacebookUpload = {
  id: string; job_id: string; clip_url: string; clip_name: string;
  kind?: 'reel' | 'story';
  status: 'queued' | 'running' | 'completed' | 'failed' | 'needs_review';
  message: string; upload_confirmed: boolean; video_url?: string | null;
  submission_started: boolean; caption: string;
  title?: string; created_at?: string;
  local_cleanup?: {state: 'deleting' | 'deleted' | 'missing' | 'error'; freed_bytes: number;
    removed_files: number; completed_at?: string; error?: string};
};
export type FacebookQC = {decision: 'HOLD' | 'PASS_UPLOAD'; issues: string[]; caption?: string;
  monetization?: {state: string; label: string; message: string}};
export type FacebookActivity = {
  checked_at: string | null; period_label: string | null; percent: number | null;
  tasks: {key: string; label: string; completed: number; target: number}[];
  stories: {completed: number; target: number} | null; note: string; href: string;
};
export type FacebookAutoRun = {
  key: string; kind: 'reel' | 'story'; title: string; status: string; job_id: string;
  progress_percent: number; message?: string; created_at: string; video_url?: string | null;
};
export type FacebookAutopilot = {
  version: number; config: {enabled: boolean; weekly_posts: number; weekly_stories: number; timezone: string};
  week_start: string; week_end: string; runtime_state: string; scheduler_running: boolean;
  confirmed_posts: number; confirmed_stories: number; produced: number; active: FacebookAutoRun | null;
  next_slot: {due_at: string; kind: string} | null; runs: FacebookAutoRun[];
  activity: FacebookActivity | null; activity_error?: string | null; message?: string; heartbeat?: string;
  bonus_priority?: {state: string; priority: boolean; amount_usd: number | null; required_reels: number | null;
    facebook_completed_reels: number | null; locally_confirmed_reels: number; minimum_duration_seconds: number | null;
    minimum_qualified_views: number | null; minimum_reels_with_qualified_views: number | null;
    period_label: string | null; checked_at: string | null; awarded: boolean; note: string};
};
export type FacebookBrief = {key: string; title: string; hook: string; recording: string; caption: string;
  target_seconds: number; max_seconds: number; state: string; sequence: string[]; proof: string};
export type FacebookMonetization = {
  version: number; checked_at: string | null; account_verified: boolean;
  check_state: 'idle' | 'running' | 'failed'; last_error?: string | null;
  program: {state: 'active' | 'restricted' | 'unknown'; evidence: string | null};
  policy: {state: 'clear' | 'restricted' | 'unknown'};
  earnings: {estimated_usd: number | null; period: string | null; qualified_views: number | null;
    rate_usd_per_1000: number | null; non_qualified_reasons: {label: string; percent: number}[]};
  bonus: {amount_usd: number | null; required_reels: number | null; minimum_duration_seconds: number | null;
    minimum_qualified_views: number | null; minimum_reels_with_qualified_views: number | null;
    completed_reels: number | null; days_remaining_at_check: number | null; period_label: string | null; awarded: boolean} | null;
  payout: {state: 'ready' | 'action_required' | 'unknown'; message: string; issues: string[]};
  insights: {period: string | null; views: number | null; three_second_views: number | null};
  actions: {key: string; priority: string; title: string; detail: string; href: string; state?: string}[];
  production_briefs: FacebookBrief[]; links: Record<string, string>; limits: string;
  confirmed_local_uploads?: number;
};

export async function facebookRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}/api/${path}`, {
    method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
    headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(path.includes('session') || path === 'social/login' ? 120_000 : 45_000),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(typeof payload?.detail === 'string' ? payload.detail :
      response.status === 404 ? 'Fitur Facebook belum aktif pada backend yang berjalan.' : 'Facebook belum dapat diakses. Coba periksa koneksi.');
  }
  return response.json() as Promise<T>;
}

export const mediaUrl = (path: string) => path.startsWith('/') ? `${API_BASE}${path}` : path;
