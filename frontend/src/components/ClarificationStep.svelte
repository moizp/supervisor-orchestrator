<script lang="ts">
  interface Props {
    question: string;
    answerText: string;
    canAnswer: boolean;
    errorMessage: string | null;
    onsubmit: () => void;
  }

  let { question, answerText = $bindable(), canAnswer, errorMessage, onsubmit }: Props = $props();

  function handleSubmit(event: SubmitEvent): void {
    event.preventDefault();
    onsubmit();
  }

  let textareaEl = $state<HTMLTextAreaElement | undefined>();

  $effect(() => {
    // Move focus to the answer field whenever a new question arrives —
    // question is read here so this effect re-runs per round.
    question;
    textareaEl?.focus();
  });
</script>

<form class="flex flex-col gap-5" onsubmit={handleSubmit}>
  <div class="flex flex-col gap-1.5">
    <span id="clarification-question-label" class="text-sm font-medium text-ink dark:text-ink-dark">
      A couple of questions before we can finish this:
    </span>
    <pre
      id="clarification-question"
      class="rounded-lg border border-mist bg-cloud px-3 py-2 text-sm whitespace-pre-wrap text-ink dark:border-mist-dark dark:bg-surface-dark dark:text-ink-dark">{question}</pre>
  </div>

  <div class="flex flex-col gap-1.5">
    <label for="answer" class="text-sm font-medium text-ink dark:text-ink-dark">
      Your answer
    </label>
    <textarea
      id="answer"
      bind:this={textareaEl}
      bind:value={answerText}
      aria-labelledby="clarification-question-label"
      rows="4"
      required
      placeholder="Answer all of the above together, in whatever order makes sense..."
      class="w-full resize-y rounded-lg border border-ink bg-white px-3 py-2 text-sm text-ink shadow-sm focus:outline-none dark:border-mist-dark dark:bg-surface-dark-2 dark:text-ink-dark"
    ></textarea>
  </div>

  {#if errorMessage}
    <p role="alert" class="text-sm font-medium text-error dark:text-error-dark">{errorMessage}</p>
  {/if}

  <button
    type="submit"
    disabled={!canAnswer}
    class="inline-flex items-center justify-center rounded-lg bg-primary-3 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-graphite focus:outline-none disabled:cursor-not-allowed disabled:bg-mist disabled:text-steel dark:disabled:bg-mist-dark dark:disabled:text-steel-dark"
  >
    Send answer
  </button>
</form>
