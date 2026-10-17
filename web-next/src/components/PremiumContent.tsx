"use client";

import { useState } from "react";

import { api, type BillingPlan } from "@/lib/api";

const TIER_LABELS: Record<BillingPlan["tier"], string> = {
  pro: "Pro",
  front_office: "Front Office",
};

function PlanCard({ plan }: { plan: BillingPlan }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const subscribe = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.startBillingCheckout(plan.tier, plan.interval);
      window.location.href = result.checkout_url;
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : "Could not start checkout.");
    }
  };

  return (
    <div
      className="p-4 flex flex-col gap-2"
      style={{
        background: "var(--color-surface-secondary)",
        border: `var(--border-width-default) solid ${plan.tier === "front_office" ? "var(--color-premium)" : "var(--color-border)"}`,
      }}
    >
      <span
        className="text-xs font-bold uppercase"
        style={{ color: plan.tier === "front_office" ? "var(--color-premium)" : "var(--color-text-muted)" }}
      >
        {TIER_LABELS[plan.tier]} — {plan.label}
      </span>
      <span style={{ font: "var(--type-primary-metric)" }}>
        {plan.price} <span className="text-sm font-normal">{plan.cadence}</span>
      </span>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <button
        type="button"
        onClick={subscribe}
        disabled={busy}
        className="px-4 py-2 text-sm font-bold self-start"
        style={{
          background: "var(--color-accent-strong)",
          color: "var(--color-brand-mark-ink)",
          fontWeight: "var(--font-weight-button)",
          opacity: busy ? "var(--opacity-disabled)" : 1,
        }}
      >
        {busy ? "Starting checkout…" : "Subscribe"}
      </button>
    </div>
  );
}

function ManageBilling() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openPortal = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.openBillingPortal();
      window.location.href = result.portal_url;
    } catch (err) {
      setBusy(false);
      setError(err instanceof Error ? err.message : "Could not open the billing portal.");
    }
  };

  return (
    <div
      className="p-4 flex flex-col gap-2"
      style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-action)" }}
    >
      <p className="text-sm font-bold">You&apos;re on Premium.</p>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Manage your plan, payment method, or cancel anytime.
      </p>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <button
        type="button"
        onClick={openPortal}
        disabled={busy}
        className="px-4 py-2 text-sm font-bold self-start"
        style={{
          background: "var(--color-premium)",
          color: "var(--color-bg)",
          opacity: busy ? "var(--opacity-disabled)" : 1,
        }}
      >
        {busy ? "Opening…" : "Manage Billing"}
      </button>
    </div>
  );
}

export function PremiumContent({
  entitlement,
  plans,
}: {
  entitlement: "free" | "premium";
  plans: BillingPlan[];
}) {
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-6 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Premium
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Unlock the full GM toolkit</h1>
      </header>

      {entitlement === "premium" ? <ManageBilling /> : null}

      <section className="flex flex-col gap-3" aria-labelledby="plans-heading">
        <h2 id="plans-heading" style={{ font: "var(--type-section-title)" }}>
          Plans
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {plans.map((plan) => (
            <PlanCard key={`${plan.tier}-${plan.interval}`} plan={plan} />
          ))}
        </div>
      </section>
    </main>
  );
}
