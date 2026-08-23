<script lang="ts">
  import { SubmissionFlow } from './lib/SubmissionFlow.svelte';
  import BackendHealthBadge from './components/BackendHealthBadge.svelte';
  import StatusMessage from './components/StatusMessage.svelte';
  import IntakeForm from './components/IntakeForm.svelte';
  import DomainReveal from './components/DomainReveal.svelte';
  import ClarificationStep from './components/ClarificationStep.svelte';
  import ResultPanel from './components/ResultPanel.svelte';

  const flow = new SubmissionFlow();

  $effect(() => {
    flow.init();
    return () => flow.destroy();
  });
</script>

<div class="min-h-screen bg-cloud px-4 py-10 dark:bg-surface-dark">
  <div class="mx-auto flex max-w-xl flex-col gap-6">
    <header class="flex items-center justify-between gap-3">
      <div>
        <h1 class="text-xl font-bold text-ink dark:text-ink-dark">llm-supervisor</h1>
        <p class="text-sm text-steel dark:text-steel-dark">
          Hazard reports and OIA requests, sorted automatically.
        </p>
      </div>
      <BackendHealthBadge status={flow.backendStatus} />
    </header>

    <main
      class="rounded-xl border border-mist bg-white p-6 shadow-sm dark:border-mist-dark dark:bg-surface-dark-2"
    >
      {#if flow.step === 'resuming'}
        <StatusMessage message="Loading your submission..." />
      {:else if flow.step === 'intake'}
        <IntakeForm
          bind:rawText={flow.rawText}
          bind:suburb={flow.suburb}
          canSubmit={flow.canSubmit}
          errorMessage={flow.errorMessage}
          onsubmit={() => flow.submit()}
        />
      {:else if flow.step === 'submitting'}
        <StatusMessage message={flow.statusMessage} />
      {:else if flow.step === 'clarifying'}
        <div class="flex flex-col gap-5">
          <DomainReveal domain={flow.domain} />
          <ClarificationStep
            question={flow.question ?? ''}
            bind:answerText={flow.answerText}
            canAnswer={flow.canAnswer}
            errorMessage={flow.errorMessage}
            onsubmit={() => flow.submitAnswer()}
          />
        </div>
      {:else if flow.step === 'answering' || flow.step === 'switching'}
        <div class="flex flex-col gap-5">
          <DomainReveal domain={flow.domain} />
          <StatusMessage message={flow.statusMessage} />
        </div>
      {:else if flow.step === 'complete'}
        <div class="flex flex-col gap-5">
          <DomainReveal domain={flow.domain} />
          <ResultPanel
            domain={flow.domain}
            result={flow.result}
            misrouteSuggestion={flow.misrouteSuggestion}
            onswitch={() => flow.doSwitch()}
            onstartover={() => flow.startOver()}
          />
        </div>
      {/if}
    </main>
  </div>
</div>
