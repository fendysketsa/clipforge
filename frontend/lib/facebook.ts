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
  status: 'queued' | 'running' | 'completed' | 'failed' | 'needs_review';
  message: string; upload_confirmed: boolean; video_url?: string | null;
  submission_started: boolean; caption: string;
};
export type FacebookQC = {decision: 'HOLD' | 'PASS_UPLOAD'; issues: string[]; caption?: string};

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
