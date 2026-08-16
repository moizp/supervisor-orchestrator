<script lang="ts">
  interface Props {
    rawText: string;
    suburb: string;
    canSubmit: boolean;
    errorMessage: string | null;
    onsubmit: () => void;
  }

  let {
    rawText = $bindable(),
    suburb = $bindable(),
    canSubmit,
    errorMessage,
    onsubmit,
  }: Props = $props();

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    onsubmit();
  }
</script>

<form class="flex flex-col gap-5" onsubmit={handleSubmit}>
  <div class="flex flex-col gap-1.5">
    <label for="raw-text" class="text-sm font-medium text-slate-700 dark:text-slate-200">
      What's going on?
    </label>
    <p id="raw-text-hint" class="text-xs text-slate-500 dark:text-slate-400">
      Describe a hazard you've noticed, or an Official Information Act request — no need to say
      which. We'll work that out.
    </p>
    <textarea
      id="raw-text"
      bind:value={rawText}
      aria-describedby="raw-text-hint"
      rows="6"
      required
      placeholder="e.g. There's a large pothole on Willis Street outside number 42, been there for weeks and getting worse..."
      class="w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/40 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
    ></textarea>
  </div>

  <div class="flex flex-col gap-1.5">
    <label for="suburb" class="text-sm font-medium text-slate-700 dark:text-slate-200">
      Suburb <span class="font-normal text-slate-400">(optional)</span>
    </label>
    <input
      id="suburb"
      type="text"
      bind:value={suburb}
      placeholder="e.g. Kilbirnie"
      class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/40 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
    />
  </div>

  {#if errorMessage}
    <p role="alert" class="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
  {/if}

  <button
    type="submit"
    disabled={!canSubmit}
    class="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 focus:ring-2 focus:ring-indigo-500/40 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500 dark:disabled:bg-slate-700 dark:disabled:text-slate-400"
  >
    Submit
  </button>
</form>
