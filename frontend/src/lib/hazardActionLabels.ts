/**
 * Friendly phrasing for the closed vocabulary of hazard "next step" action
 * codes returned by the hazard triage backend (see
 * wellington-impact-lab/backend/app/clarifier.py's ACTION_VOCABULARY).
 * Mirrors the DOMAIN_LABELS lookup pattern in domainLabels.ts.
 */
export const HAZARD_ACTION_LABELS: Record<string, string> = {
  check_neighbours: 'Check on your neighbours',
  monitor_situation: 'Monitor the situation',
  document_further: "Take photos or notes if it's safe to do so",
  call_111: "Call 111 if there's immediate danger",
  evacuate: "Evacuate the area if it's safe to do so",
  none: 'No further action needed',
};
