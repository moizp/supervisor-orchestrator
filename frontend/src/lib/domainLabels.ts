import type { Domain } from './api';

/**
 * Shared vocabulary for naming the two pipelines an assigned request can
 * belong to. Used by both the persistent pipeline badge (PipelineBadge) and
 * the misroute cross-check line in ResultPanel, so the two stay in sync.
 */
export const DOMAIN_LABELS: Record<Domain, string> = {
  hazard: 'Hazard Triage',
  oia: 'OIA Routing',
};
