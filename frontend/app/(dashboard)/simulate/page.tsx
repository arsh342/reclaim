import { SimulatorForm } from "@/components/simulator-form";
import { PageHeader, PageShell } from "@/components/page-shell";

export default function SimulatePage() {
  return (
    <PageShell className="max-w-5xl">
      <PageHeader
        eyebrow="Simulator / controlled event"
        title="Fire a webhook. Watch Reclaim decide."
        description="Send a synthetic payment event through the same ingestion path used by the recovery engine."
        meta={<span className="num text-xs uppercase tracking-widest text-ink-faint">POST /webhooks/simulate</span>}
      />

      <div className="mb-8 grid gap-3 sm:grid-cols-3">
        <div className="border-l-2 border-rule-strong pl-4">
          <p className="eyebrow">01 / send</p>
          <p className="mt-2 text-sm text-ink-muted">Build a payment event.</p>
        </div>
        <div className="border-l-2 border-rule pl-4">
          <p className="eyebrow">02 / decide</p>
          <p className="mt-2 text-sm text-ink-muted">Policy ranks recovery options.</p>
        </div>
        <div className="border-l-2 border-rule pl-4">
          <p className="eyebrow">03 / inspect</p>
          <p className="mt-2 text-sm text-ink-muted">Open the resulting case file.</p>
        </div>
      </div>

      <SimulatorForm />
    </PageShell>
  );
}
