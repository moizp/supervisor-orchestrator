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
    <span
      id="clarification-question-label"
      class="text-sm font-medium text-slate-700 dark:text-slate-200"
    >
      A couple of questions before we can finish this:
    </span>
    <pre
      id="clarification-question"
      class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm whitespace-pre-wrap text-slate-800 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100">{question}</pre>
  </div>

  <div class="flex flex-col gap-1.5">
    <label for="answer" class="text-sm font-medium text-slate-700 dark:text-slate-200">
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
      class="w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/40 focus:outline-none dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
    ></textarea>
  </div>

  {#if errorMessage}
    <p role="alert" class="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
  {/if}

  <button
    type="submit"
    disabled={!canAnswer}
    class="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 focus:ring-2 focus:ring-indigo-500/40 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500 dark:disabled:bg-slate-700 dark:disabled:text-slate-400"
  >
    Send answer
  </button>
</form>
