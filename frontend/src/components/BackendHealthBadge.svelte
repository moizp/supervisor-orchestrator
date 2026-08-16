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
      ? 'bg-emerald-500'
      : status === 'offline'
        ? 'bg-red-500'
        : 'bg-amber-400 animate-pulse'
  );
</script>

<div
  class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-2.5 py-1 text-xs text-slate-600 shadow-sm dark:border-slate-700 dark:bg-slate-800/80 dark:text-slate-300"
  title={label}
  role="status"
>
  <span class={['h-2 w-2 rounded-full', dotClass]} aria-hidden="true"></span>
  <span class="hidden sm:inline">{label}</span>
</div>
