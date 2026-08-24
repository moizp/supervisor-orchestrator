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
    <label for="raw-text" class="text-sm font-medium text-ink dark:text-ink-dark">
      Report hazard or submit OIA request
    </label>
    <p id="raw-text-hint" class="text-xs text-steel dark:text-steel-dark">
      Describe a hazard you've noticed, or an Official Information Act request. (No need to say
      which — We'll work that out.)
    </p>
    <textarea
      id="raw-text"
      bind:value={rawText}
      aria-describedby="raw-text-hint"
      rows="6"
      required
      placeholder="e.g. There's a large pothole on Willis Street outside number 42, been there for weeks and getting worse..."
      class="w-full resize-y rounded-lg border border-ink bg-white px-3 py-2 text-sm text-ink shadow-sm focus:outline-none dark:border-mist-dark dark:bg-surface-dark-2 dark:text-ink-dark"
    ></textarea>
  </div>

  <div class="flex flex-col gap-1.5">
    <label for="suburb" class="text-sm font-medium text-ink dark:text-ink-dark">
      Suburb <span class="font-normal text-steel dark:text-steel-dark">(optional)</span>
    </label>
    <input
      id="suburb"
      type="text"
      bind:value={suburb}
      placeholder="e.g. Kilbirnie"
      class="w-full rounded-lg border border-ink bg-white px-3 py-2 text-sm text-ink shadow-sm focus:outline-none dark:border-mist-dark dark:bg-surface-dark-2 dark:text-ink-dark"
    />
  </div>

  {#if errorMessage}
    <p role="alert" class="text-sm font-medium text-error dark:text-error-dark">{errorMessage}</p>
  {/if}

  <button
    type="submit"
    disabled={!canSubmit}
    class="inline-flex items-center justify-center rounded-lg bg-primary-3 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-graphite focus:outline-none disabled:cursor-not-allowed disabled:bg-mist disabled:text-steel dark:disabled:bg-mist-dark dark:disabled:text-steel-dark"
  >
    Submit
  </button>
</form>
