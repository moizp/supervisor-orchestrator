import {
  ApiError,
  answerSubmission,
  checkBackendHealth,
  getSubmission,
  submitReport,
  switchDomain,
  warmupRouter,
  type Domain,
  type Location,
  type SubmissionResponse,
  type SubmissionResult,
} from './api';

export type FlowStep =
  'resuming' | 'intake' | 'submitting' | 'clarifying' | 'answering' | 'switching' | 'complete';

export type BackendStatus = 'checking' | 'online' | 'offline';

interface StatusStage {
  delayMs: number;
  text: string;
}

// Staged, plausible-progress messages for the initial /submit call. Domain
// isn't known yet at this point (that's what the call determines), so these
// stay generic rather than claiming a specific pipeline is running.
const SUBMIT_STAGES: StatusStage[] = [
  { delayMs: 0, text: 'Reading your submission...' },
  { delayMs: 3000, text: 'Figuring out where this should go...' },
  {
    delayMs: 10000,
    text: 'Still working on it — hazard reports can take up to a minute to triage; OIA requests are usually quicker.',
  },
  { delayMs: 30000, text: 'Still going — thanks for bearing with us.' },
  { delayMs: 60000, text: 'Almost there, finishing up...' },
];

const HAZARD_ANSWER_STAGES: StatusStage[] = [
  { delayMs: 0, text: 'Recording your answer...' },
  { delayMs: 3000, text: 'Checking with the triage system...' },
  { delayMs: 15000, text: 'Still checking — this can take up to a minute for hazard reports.' },
  { delayMs: 45000, text: 'Almost there...' },
];

const OIA_ANSWER_STAGES: StatusStage[] = [
  { delayMs: 0, text: 'Recording your answer...' },
  { delayMs: 2000, text: 'Reviewing your response...' },
  { delayMs: 6000, text: 'Almost there...' },
];

const SWITCH_STAGES: StatusStage[] = [
  { delayMs: 0, text: 'Restarting under the other pipeline...' },
  { delayMs: 4000, text: 'Still working on it...' },
];

const HEALTH_POLL_INTERVAL_MS = 30000;

function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 0) return err.message;
    if (err.status === 404) return 'That submission could not be found — it may have expired.';
    if (err.status === 400) return err.message || 'That action is not valid for this submission.';
    return err.message || `The orchestrator API returned an error (${err.status}).`;
  }
  return 'Something unexpected went wrong talking to the orchestrator API.';
}

export class SubmissionFlow {
  step = $state<FlowStep>('intake');
  rawText = $state('');
  suburb = $state('');
  sessionId = $state<string | null>(null);
  domain = $state<Domain | null>(null);
  question = $state<string | null>(null);
  answerText = $state('');
  result = $state<SubmissionResult | null>(null);
  misrouteSuggestion = $state<Domain | null>(null);
  statusMessage = $state('');
  errorMessage = $state<string | null>(null);
  backendStatus = $state<BackendStatus>('checking');

  private statusTimers: ReturnType<typeof setTimeout>[] = [];
  private healthTimer: ReturnType<typeof setInterval> | undefined;

  get canSubmit(): boolean {
    return this.rawText.trim().length > 0;
  }

  get canAnswer(): boolean {
    return this.answerText.trim().length > 0;
  }

  /** Called once from the root component's $effect on mount. */
  init(): void {
    warmupRouter();
    void this.checkHealth();
    this.healthTimer = setInterval(() => void this.checkHealth(), HEALTH_POLL_INTERVAL_MS);

    const params = new URLSearchParams(window.location.search);
    const existingSession = params.get('session');
    if (existingSession) {
      void this.resumeSession(existingSession);
    } else {
      this.step = 'intake';
    }
  }

  destroy(): void {
    this.clearStagedStatus();
    if (this.healthTimer) clearInterval(this.healthTimer);
  }

  private async checkHealth(): Promise<void> {
    const online = await checkBackendHealth();
    this.backendStatus = online ? 'online' : 'offline';
  }

  private beginStagedStatus(stages: StatusStage[]): void {
    this.clearStagedStatus();
    if (stages.length === 0) return;
    this.statusMessage = stages[0].text;
    for (const stage of stages.slice(1)) {
      const timer = setTimeout(() => {
        this.statusMessage = stage.text;
      }, stage.delayMs);
      this.statusTimers.push(timer);
    }
  }

  private clearStagedStatus(): void {
    for (const timer of this.statusTimers) clearTimeout(timer);
    this.statusTimers = [];
  }

  private reflectSessionInUrl(sessionId: string): void {
    const url = new URL(window.location.href);
    url.searchParams.set('session', sessionId);
    window.history.replaceState(null, '', url);
  }

  private clearSessionFromUrl(): void {
    const url = new URL(window.location.href);
    url.searchParams.delete('session');
    window.history.replaceState(null, '', url);
  }

  private applyResponse(resp: SubmissionResponse): void {
    this.sessionId = resp.session_id;
    this.domain = resp.domain;
    this.reflectSessionInUrl(resp.session_id);

    if (resp.status === 'awaiting_clarification') {
      this.question = resp.question ?? '';
      this.answerText = '';
      this.result = null;
      this.misrouteSuggestion = null;
      this.step = 'clarifying';
    } else {
      this.question = null;
      this.result = resp.result ?? null;
      this.misrouteSuggestion = resp.misroute_suggestion ?? null;
      this.step = 'complete';
    }
  }

  async resumeSession(sessionId: string): Promise<void> {
    this.step = 'resuming';
    this.errorMessage = null;
    try {
      const resp = await getSubmission(sessionId);
      this.backendStatus = 'online';
      this.applyResponse(resp);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 0) this.backendStatus = 'online';
      else this.backendStatus = 'offline';
      this.errorMessage = describeError(err);
      this.clearSessionFromUrl();
      this.step = 'intake';
    }
  }

  async submit(): Promise<void> {
    if (!this.canSubmit) return;
    this.errorMessage = null;
    this.step = 'submitting';
    const location: Location | undefined = this.suburb.trim()
      ? { suburb: this.suburb.trim() }
      : undefined;
    this.beginStagedStatus(SUBMIT_STAGES);
    try {
      const resp = await submitReport(this.rawText.trim(), location);
      this.backendStatus = 'online';
      this.applyResponse(resp);
    } catch (err) {
      this.backendStatus = err instanceof ApiError && err.status !== 0 ? 'online' : 'offline';
      this.errorMessage = describeError(err);
      this.step = 'intake';
    } finally {
      this.clearStagedStatus();
    }
  }

  async submitAnswer(): Promise<void> {
    if (!this.sessionId || !this.canAnswer) return;
    this.errorMessage = null;
    const answer = this.answerText.trim();
    this.step = 'answering';
    this.beginStagedStatus(this.domain === 'hazard' ? HAZARD_ANSWER_STAGES : OIA_ANSWER_STAGES);
    try {
      const resp = await answerSubmission(this.sessionId, answer);
      this.backendStatus = 'online';
      this.applyResponse(resp);
    } catch (err) {
      this.backendStatus = err instanceof ApiError && err.status !== 0 ? 'online' : 'offline';
      this.errorMessage = describeError(err);
      this.step = 'clarifying';
    } finally {
      this.clearStagedStatus();
    }
  }

  async doSwitch(): Promise<void> {
    if (!this.sessionId) return;
    this.errorMessage = null;
    this.step = 'switching';
    this.beginStagedStatus(SWITCH_STAGES);
    try {
      const resp = await switchDomain(this.sessionId);
      this.backendStatus = 'online';
      this.applyResponse(resp);
    } catch (err) {
      this.backendStatus = err instanceof ApiError && err.status !== 0 ? 'online' : 'offline';
      this.errorMessage = describeError(err);
      this.step = 'complete';
    } finally {
      this.clearStagedStatus();
    }
  }

  startOver(): void {
    this.sessionId = null;
    this.domain = null;
    this.question = null;
    this.rawText = '';
    this.suburb = '';
    this.answerText = '';
    this.result = null;
    this.misrouteSuggestion = null;
    this.errorMessage = null;
    this.clearSessionFromUrl();
    this.step = 'intake';
  }
}
