<script lang="ts">
  import type { BackendStatus } from '../lib/SubmissionFlow.svelte';

  interface Props {
    status: BackendStatus;
  }

  let { status }: Props = $props();

  const label = $derived(
    status === 'online'
      ? 'Backend connected'
      : status === 'offline'
        ? 'Backend unreachable'
        : 'Checking backend connection...'
  );

  const dotClass = $derived(
    status === 'online'
      ? 'bg-success dark:bg-success-dark'
      : status === 'offline'
        ? 'bg-error dark:bg-error-dark'
        : 'bg-warning dark:bg-warning-dark animate-pulse'
  );
</script>

<div
  class="inline-flex items-center gap-1.5 rounded-full border border-mist bg-white/80 px-2.5 py-1 text-xs text-steel shadow-sm dark:border-mist-dark dark:bg-surface-dark-2/80 dark:text-steel-dark"
  title={label}
  role="status"
>
  <span class={['h-2 w-2 rounded-full', dotClass]} aria-hidden="true"></span>
  <span class="hidden sm:inline">{label}</span>
</div>
