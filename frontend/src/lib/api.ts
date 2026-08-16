// Orchestrator API client — contract from FRONTEND_PLAN.md, implemented in
// ../../../api.py. No auth on this API (matches api.py's own comment) —
// don't add any here either.

export interface Location {
  suburb?: string;
  lat?: number;
  lon?: number;
}

export type Domain = 'hazard' | 'oia';
export type SubmissionStatus = 'awaiting_clarification' | 'complete';

export interface HazardResult {
  severity: string | null;
  rationale: string;
  hazard_type: string | null;
  actions: string[];
}

export interface OiaResult {
  agency: string;
}

export type SubmissionResult = HazardResult | OiaResult;

export interface SubmissionResponse {
  session_id: string;
  domain: Domain | null;
  status: SubmissionStatus;
  question?: string;
  result?: SubmissionResult;
  misroute_suggestion?: Domain | null;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// Fired once on app load (see SubmissionFlow.svelte.ts) to wake the router
// service before the user finishes the intake form. Cross-origin, CORS wide
// open on that service — fire-and-forget, errors swallowed by warmupRouter().
const WARMUP_URL = 'https://router-service-716627644300.australia-southeast1.run.app/warmup';

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch {
    throw new ApiError(0, 'Could not reach the orchestrator API — check your connection.');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function submitReport(rawText: string, location?: Location): Promise<SubmissionResponse> {
  return request('/submit', {
    method: 'POST',
    body: JSON.stringify({ raw_text: rawText, location }),
  });
}

export function getSubmission(sessionId: string): Promise<SubmissionResponse> {
  return request(`/submit/${encodeURIComponent(sessionId)}`, { method: 'GET' });
}

export function answerSubmission(sessionId: string, answer: string): Promise<SubmissionResponse> {
  return request(`/submit/${encodeURIComponent(sessionId)}/answer`, {
    method: 'POST',
    body: JSON.stringify({ answer }),
  });
}

export function switchDomain(sessionId: string): Promise<SubmissionResponse> {
  return request(`/submit/${encodeURIComponent(sessionId)}/switch`, { method: 'POST' });
}

// Cheap reachability probe for the backend-health indicator. A 404 (unknown
// session) is a healthy response — it means the API answered a real request.
// Only a network-level failure counts as "offline".
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/submit/__health_probe__`, {
      signal: AbortSignal.timeout(5000),
    });
    return res.status === 404 || res.ok;
  } catch {
    return false;
  }
}

export function warmupRouter(): void {
  fetch(WARMUP_URL, { mode: 'cors' }).catch(() => {
    // fire-and-forget — a failed warmup just means the first real submission
    // may hit a cold start instead. Not surfaced to the user.
  });
}
