<script lang="ts">
  interface Props {
    message: string;
  }

  let { message }: Props = $props();
</script>

<div class="flex flex-col items-center gap-4 py-12 text-center" aria-live="polite">
  <span
    class="h-8 w-8 animate-spin rounded-full border-4 border-mist border-t-info dark:border-mist-dark dark:border-t-info-dark"
    aria-hidden="true"
  ></span>
  <p class="max-w-sm text-sm font-medium text-info dark:text-info-dark">{message}</p>
</div>
