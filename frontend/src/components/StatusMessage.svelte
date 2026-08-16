<script lang="ts">
  interface Props {
    message: string;
  }

  let { message }: Props = $props();
</script>

<div class="flex flex-col items-center gap-4 py-12 text-center" aria-live="polite">
  <span
    class="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-indigo-600 dark:border-slate-700 dark:border-t-indigo-400"
    aria-hidden="true"
  ></span>
  <p class="max-w-sm text-sm text-slate-600 dark:text-slate-300">{message}</p>
</div>
