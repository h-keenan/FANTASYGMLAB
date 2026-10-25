"use client";

import Link from "next/link";

import { trackFeatureUse } from "@/lib/analytics";

import { ButtonLink } from "@/components/Button";
import { ToneBadge } from "@/components/ToneBadge";
import {
  SAMPLE_BANNER_BODY,
  SAMPLE_BANNER_TITLE,
  SAMPLE_CONNECT_ROUTE,
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
      className="glass-surface sticky top-0 z-20 flex flex-col gap-2 p-3"
      style={{ borderLeft: "var(--border-width-semantic) solid var(--color-accent)" }}
    >
      <div className="flex items-center gap-2">
        <ToneBadge label={SAMPLE_BANNER_TITLE} color="var(--color-accent)" />
        <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {SAMPLE_BANNER_BODY}
        </span>
      </div>
      <ButtonLink href={SAMPLE_CONNECT_ROUTE} size="sm" className="self-start">
        {SAMPLE_CTA_LABEL}
      </ButtonLink>
    </aside>
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
