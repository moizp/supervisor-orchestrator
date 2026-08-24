<script lang="ts">
  import type { Domain, HazardResult, OiaResult, SubmissionResult } from '../lib/api';
  import { HAZARD_ACTION_LABELS } from '../lib/hazardActionLabels';

  interface Props {
    domain: Domain | null;
    result: SubmissionResult | null;
    misrouteSuggestion: Domain | null;
    onswitch: () => void;
    onstartover: () => void;
  }

  let { domain, result, misrouteSuggestion, onswitch, onstartover }: Props = $props();

  const hazardResult = $derived(domain === 'hazard' ? (result as HazardResult | null) : null);
  const oiaResult = $derived(domain === 'oia' ? (result as OiaResult | null) : null);

  const severityClass = $derived.by(() => {
    switch (hazardResult?.severity) {
      case 'high':
        return 'bg-error/10 text-error dark:bg-error-dark/15 dark:text-error-dark';
      case 'medium':
        return 'bg-warning/10 text-warning dark:bg-warning-dark/15 dark:text-warning-dark';
      case 'low':
        return 'bg-success/10 text-success dark:bg-success-dark/15 dark:text-success-dark';
      default:
        return 'bg-cloud text-steel dark:bg-surface-dark dark:text-steel-dark';
    }
  });

  const otherDomainLabel = $derived(
    misrouteSuggestion === 'hazard' ? 'hazard report' : 'OIA request'
  );

  const hazardActions = $derived(hazardResult?.actions.filter((action) => action !== 'none') ?? []);
  const hazardNoActionNeeded = $derived(
    hazardResult !== null && hazardResult.actions.length > 0 && hazardActions.length === 0
  );
</script>

<div class="flex flex-col gap-5">
  {#if hazardResult}
    <div class="flex flex-col gap-3 rounded-lg border border-mist p-4 dark:border-mist-dark">
      <div class="flex flex-wrap items-center gap-2">
        <span class={['rounded-full px-2.5 py-1 text-xs font-semibold capitalize', severityClass]}>
          Severity: {hazardResult.severity ?? 'unknown'}
        </span>
        {#if hazardResult.hazard_type}
          <span
            class="rounded-full bg-cloud px-2.5 py-1 text-xs font-medium text-ink capitalize dark:bg-surface-dark dark:text-steel-dark"
          >
            {hazardResult.hazard_type}
          </span>
        {/if}
      </div>
      <p class="text-sm text-ink dark:text-ink-dark">{hazardResult.rationale}</p>
      {#if hazardActions.length > 0}
        <div>
          <h3 class="mb-1 text-sm font-medium text-ink dark:text-ink-dark">Next steps</h3>
          <ul class="list-inside list-disc space-y-1 text-sm text-ink dark:text-steel-dark">
            {#each hazardActions as action (action)}
              <li>{HAZARD_ACTION_LABELS[action] ?? action}</li>
            {/each}
          </ul>
        </div>
      {:else if hazardNoActionNeeded}
        <p class="text-sm text-ink dark:text-steel-dark">No further action needed</p>
      {/if}
    </div>
  {:else if oiaResult}
    <div class="flex flex-col gap-2 rounded-lg border border-mist p-4 dark:border-mist-dark">
      <h3 class="text-sm font-medium text-ink dark:text-ink-dark">Assigned agency</h3>
      <p class="text-base font-semibold text-ink dark:text-ink-dark">{oiaResult.agency}</p>
    </div>
  {:else}
    <p class="text-sm text-steel dark:text-steel-dark">No result was returned.</p>
  {/if}

  {#if misrouteSuggestion}
    <div
      class="flex flex-col gap-3 rounded-lg border border-warning bg-warning/10 p-4 dark:border-warning-dark dark:bg-warning-dark/10"
    >
      <p class="text-sm text-warning dark:text-warning-dark">
        This looks like it might fit better as a {otherDomainLabel}.
      </p>
      <button
        type="button"
        onclick={onswitch}
        class="inline-flex w-fit items-center justify-center rounded-lg border border-warning bg-white px-3 py-1.5 text-sm font-semibold text-warning shadow-sm transition-colors hover:bg-warning/10 focus:outline-none dark:border-warning-dark dark:bg-surface-dark-2 dark:text-warning-dark dark:hover:bg-surface-dark"
      >
        Submit as {otherDomainLabel}
      </button>
    </div>
  {/if}

  <button
    type="button"
    onclick={onstartover}
    class="inline-flex w-fit items-center justify-center rounded-lg border border-ink px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-cloud focus:outline-none dark:border-mist-dark dark:text-steel-dark dark:hover:bg-surface-dark"
  >
    Start a new submission
  </button>
</div>
