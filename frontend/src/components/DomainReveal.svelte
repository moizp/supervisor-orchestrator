<script lang="ts">
  import type { Domain } from '../lib/api';

  interface Props {
    domain: Domain | null;
  }

  let { domain }: Props = $props();

  const label = $derived(
    domain === 'hazard'
      ? 'This looks like a hazard report.'
      : domain === 'oia'
        ? 'This looks like an Official Information Act (OIA) request.'
        : ''
  );
</script>

{#if label}
  <p
    class="rounded-lg bg-info/10 px-3 py-2 text-sm font-medium text-info dark:bg-info-dark/10 dark:text-info-dark"
  >
    {label}
  </p>
{/if}
