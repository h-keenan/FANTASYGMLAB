"use client";

import { useSyncExternalStore } from "react";

import { ButtonLink } from "@/components/Button";
import { trackTryLink } from "@/lib/analytics";
import { TRY_CTA_LABEL, tryCtaHref, type TryTopic } from "@/lib/tryLinks";

const subscribeNever = () => () => {};

/**
 * The ONE call to action that ends every /try/<topic> page. The href carries the visitor's own campaign params
 * (utm params, click ids, ref) into connect-league so the touch survives auth and onboarding even where storage is blocked
 * (lib/tryLinks.tryCtaHref). The click is counted as feature_use feature=try_link action=cta_click (demo).
 */
export function TryCta({ topic }: { topic: TryTopic }) {
  // "" on the server and during hydration, then the live query string (the visitor's own campaign params).
  const search = useSyncExternalStore(subscribeNever, () => window.location.search, () => "");
  const href = tryCtaHref(topic, search);
  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-label={TRY_CTA_LABEL} data-testid="try-cta">
      <h2 style={{ font: "var(--type-section-title)" }}>This was an example league</h2>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Connect your Sleeper league and get this on your real roster, in about a minute. No card needed.
      </p>
      <ButtonLink href={href} variant="primary" fullWidth data-testid="try-cta-link" onClick={() => trackTryLink("cta_click", topic)}>
        {TRY_CTA_LABEL}
      </ButtonLink>
    </section>
  );
}
