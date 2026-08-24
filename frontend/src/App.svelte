<script lang="ts">
  import { SubmissionFlow } from './lib/SubmissionFlow.svelte';
  import BackendHealthBadge from './components/BackendHealthBadge.svelte';
  import PipelineBadge from './components/PipelineBadge.svelte';
  import StatusMessage from './components/StatusMessage.svelte';
  import IntakeForm from './components/IntakeForm.svelte';
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
        <h1 class="text-xl font-bold text-ink dark:text-ink-dark">Smart Supervisor</h1>
        <p class="text-sm text-steel dark:text-steel-dark">
          Hazard reports and OIA requests, identified and routed automatically.
        </p>
      </div>
      <div class="flex items-center gap-2">
        {#if flow.domain}
          <PipelineBadge domain={flow.domain} />
        {/if}
        <BackendHealthBadge status={flow.backendStatus} />
      </div>
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
        <ClarificationStep
          question={flow.question ?? ''}
          bind:answerText={flow.answerText}
          canAnswer={flow.canAnswer}
          errorMessage={flow.errorMessage}
          onsubmit={() => flow.submitAnswer()}
        />
      {:else if flow.step === 'answering' || flow.step === 'switching'}
        <StatusMessage message={flow.statusMessage} />
      {:else if flow.step === 'complete'}
        <ResultPanel
          domain={flow.domain}
          result={flow.result}
          misrouteSuggestion={flow.misrouteSuggestion}
          onswitch={() => flow.doSwitch()}
          onstartover={() => flow.startOver()}
        />
      {/if}
    </main>
  </div>
</div>
