<script lang="ts">
  import { fade } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import type { Domain } from '../lib/api';
  import { DOMAIN_LABELS } from '../lib/domainLabels';

  interface Props {
    domain: Domain;
  }

  let { domain }: Props = $props();

  const label = $derived(DOMAIN_LABELS[domain]);
</script>

<div
  class="inline-flex items-center gap-1.5 rounded-full border border-mist bg-white/80 px-2.5 py-1 text-xs font-medium text-ink shadow-sm dark:border-mist-dark dark:bg-surface-dark-2/80 dark:text-ink-dark"
  role="status"
  title="Assigned pipeline: {label}"
  in:fade={{ duration: prefersReducedMotion.current ? 0 : 200 }}
>
  {#if domain === 'hazard'}
    <svg
      viewBox="0 0 20 20"
      fill="none"
      class="h-3.5 w-3.5 text-primary-3 dark:text-primary"
      aria-hidden="true"
    >
      <path
        d="M10 2.5 1.5 17h17L10 2.5Z"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linejoin="round"
      />
      <path d="M10 8v3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      <circle cx="10" cy="14" r="0.9" fill="currentColor" />
    </svg>
  {:else}
    <svg
      viewBox="0 0 20 20"
      fill="none"
      class="h-3.5 w-3.5 text-primary-3 dark:text-primary"
      aria-hidden="true"
    >
      <path
        d="M5 2.5h7l3 3v12h-10v-15Z"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linejoin="round"
      />
      <path
        d="M7.5 10h5M7.5 13h5"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
      />
    </svg>
  {/if}
  <span class="hidden sm:inline">{label}</span>
</div>
