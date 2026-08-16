<script lang="ts">
  import type { Domain, HazardResult, OiaResult, SubmissionResult } from '../lib/api';

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
        return 'bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-200';
      case 'medium':
        return 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-200';
      case 'low':
        return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200';
      default:
        return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
    }
  });

  const otherDomainLabel = $derived(
    misrouteSuggestion === 'hazard' ? 'hazard report' : 'OIA request'
  );
</script>

<div class="flex flex-col gap-5">
  {#if hazardResult}
    <div class="flex flex-col gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-700">
      <div class="flex flex-wrap items-center gap-2">
        <span class={['rounded-full px-2.5 py-1 text-xs font-semibold capitalize', severityClass]}>
          Severity: {hazardResult.severity ?? 'unknown'}
        </span>
        {#if hazardResult.hazard_type}
          <span
            class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 capitalize dark:bg-slate-800 dark:text-slate-300"
          >
            {hazardResult.hazard_type}
          </span>
        {/if}
      </div>
      <p class="text-sm text-slate-700 dark:text-slate-200">{hazardResult.rationale}</p>
      {#if hazardResult.actions.length > 0}
        <div>
          <h3 class="mb-1 text-sm font-medium text-slate-700 dark:text-slate-200">Next steps</h3>
          <ul class="list-inside list-disc space-y-1 text-sm text-slate-600 dark:text-slate-300">
            {#each hazardResult.actions as action (action)}
              <li>{action}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  {:else if oiaResult}
    <div class="flex flex-col gap-2 rounded-lg border border-slate-200 p-4 dark:border-slate-700">
      <h3 class="text-sm font-medium text-slate-700 dark:text-slate-200">Assigned agency</h3>
      <p class="text-base font-semibold text-slate-900 dark:text-slate-50">{oiaResult.agency}</p>
    </div>
  {:else}
    <p class="text-sm text-slate-500 dark:text-slate-400">No result was returned.</p>
  {/if}

  {#if misrouteSuggestion}
    <div
      class="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-950/40"
    >
      <p class="text-sm text-amber-900 dark:text-amber-100">
        This looks like it might fit better as a {otherDomainLabel}.
      </p>
      <button
        type="button"
        onclick={onswitch}
        class="inline-flex w-fit items-center justify-center rounded-lg border border-amber-400 bg-white px-3 py-1.5 text-sm font-semibold text-amber-800 shadow-sm transition-colors hover:bg-amber-100 focus:ring-2 focus:ring-amber-500/40 focus:outline-none dark:border-amber-600 dark:bg-slate-900 dark:text-amber-200 dark:hover:bg-slate-800"
      >
        Submit as {otherDomainLabel}
      </button>
    </div>
  {/if}

  <button
    type="button"
    onclick={onstartover}
    class="inline-flex w-fit items-center justify-center rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 focus:ring-2 focus:ring-indigo-500/40 focus:outline-none dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
  >
    Start a new submission
  </button>
</div>
