"use client";

import Link from "next/link";

import { trackFeatureUse } from "@/lib/analytics";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { ToneBadge } from "@/components/ToneBadge";
import {
  SAMPLE_BANNER_BODY,
  SAMPLE_BANNER_TITLE,
  SAMPLE_CONNECT_BODY,
  SAMPLE_CONNECT_ROUTE,
  SAMPLE_CONNECT_TITLE,
  SAMPLE_CTA_LABEL,
  SAMPLE_ENTRY_LABEL,
  SAMPLE_ROUTE,
  SAMPLE_TRY_LABEL,
} from "@/lib/sampleLeague";

/**
 * Persistent "Sample league" label + connect CTA, shown on every tab of the
 * sample league. Mobile twin: mobile/src/components/SampleLeagueBanner.tsx.
 */
export function SampleLeagueBanner() {
  return (
    <aside
      role="note"
      data-testid="sample-banner"
      className="glass-surface sticky top-2 z-30 flex items-center gap-2 px-3 py-1.5"
      style={{ borderLeft: "var(--border-width-semantic) solid var(--color-accent)" }}
    >
      <span className="shrink-0"><ToneBadge label={SAMPLE_BANNER_TITLE} color="var(--color-accent)" /></span>
      <span className="min-w-0 flex-1 truncate text-xs max-sm:sr-only" style={{ color: "var(--color-text-secondary)" }}>
        {SAMPLE_BANNER_BODY}
      </span>
      <ButtonLink href={SAMPLE_CONNECT_ROUTE} size="sm" className="ml-auto shrink-0">
        {SAMPLE_CTA_LABEL}
      </ButtonLink>
    </aside>
  );
}

/** The closing module of a sample tab: what the real thing would show, with the one way to get it. */
export function SampleConnectModule() {
  return (
    <AccentCard accent="var(--color-accent)" data-testid="sample-connect-module">
      <h3 style={{ font: "var(--font-card-title)" }}>{SAMPLE_CONNECT_TITLE}</h3>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {SAMPLE_CONNECT_BODY}
      </p>
      <ButtonLink href={SAMPLE_CONNECT_ROUTE} fullWidth>
        {SAMPLE_CTA_LABEL}
      </ButtonLink>
    </AccentCard>
  );
}

/** Quiet entry point under the "connect a league" forms. */
export function SampleLeagueLink() {
  return (
    <Link
      href={SAMPLE_ROUTE}
      data-testid="sample-league-link"
      className="text-sm font-bold text-center inline-flex items-center justify-center min-h-[var(--touch-target-min)]"
      style={{ color: "var(--color-accent)" }}
    >
      {SAMPLE_ENTRY_LABEL}
    </Link>
  );
}

/**
 * Prominent "Try a sample league" button for the landing page, the connect
 * step and connect-error states. Opens the existing static sample league
 * (no new data). The click is tracked on web only (the app's analytics stay
 * off); `surface` is a fixed snake_case id, never free text.
 */
export function SampleLeagueButton({
  surface,
  variant = "secondary",
  fullWidth = true,
}: {
  surface: "landing_hero" | "connect_step" | "connect_error";
  variant?: "primary" | "secondary";
  fullWidth?: boolean;
}) {
  return (
    <ButtonLink
      href={SAMPLE_ROUTE}
      variant={variant}
      fullWidth={fullWidth}
      data-testid="sample-league-button"
      onClick={() => trackFeatureUse("sample_league_cta_clicked", { dedupe: false, props: { source_surface: surface } })}
    >
      {SAMPLE_TRY_LABEL}
    </ButtonLink>
  );
}
