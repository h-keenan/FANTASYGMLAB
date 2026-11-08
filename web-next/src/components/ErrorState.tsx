"use client";

import { useEffect } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyStateGlyph, StateIconRing } from "@/components/EmptyState";
import { trackClientError } from "@/lib/analytics";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { FREE_LEAGUE_CAP_MESSAGE } from "@/lib/freeLeagueCap";

/** True for a raw exception string (not a sentence written for the user). */
export function looksTechnical(message: string): boolean {
  return (
    /\b(TypeError|ReferenceError|SyntaxError|RangeError|undefined|is not (iterable|a function|defined)|cannot read|unexpected token|JSON|NaN)\b/i.test(message) ||
    /\b\w+(\.\w+)+ is\b/.test(message) ||
    message.length > 200
  );
}

/**
 * Shared "couldn't load" state with a real way back — coridian_, 2026-10-18,
 * screenshot: backgrounding Safari and returning to the app left a bare
 * "The request timed out" message with no recovery, just a dead page (the
 * 30s client-side AbortController in lib/api.ts's fetchJson fires almost
 * immediately on resume, since Safari suspends an in-flight fetch's timer
 * while backgrounded — the elapsed wall-clock time is already past 30s by
 * the time the tab wakes back up). Every page that fetches its own data
 * had its own copy of a bare `<p role="alert">{error}</p>` with no retry
 * affordance at all — this is that block, with a real "Try again" button.
 *
 * A danger-railed AccentCard with the shared icon ring. Messages written for
 * the user show as is; a raw exception string ("x.players is not iterable")
 * is replaced by friendly copy and kept behind a "Details" disclosure.
 *
 * `onRetry` is optional only for messages that no retry can fix (e.g.
 * Player Compare's "No player selected to compare."). A page whose own
 * fetch effect has no retry token can pass `reloadPage`.
 */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const leagueLocked = message === FREE_LEAGUE_CAP_MESSAGE;
  const technical = looksTechnical(message);
  // Team-visible error signal (route_error): only a coarse class derived from
  // the message, never the message itself. Rate limited in trackClientError.
  useEffect(() => {
    trackClientError("route_error", null, { status: /timed out|could not reach/i.test(message) ? 0 : undefined });
  }, [message]);
  if (leagueLocked) {
    return (
      <PremiumUpsellCard
        kicker="Free plan"
        upsell={null}
        fallbackTitle="Your Free plan includes one league"
        fallbackBody={message}
      />
    );
  }
  return (
    <main className="flex-1 flex flex-col justify-center px-4 py-8 max-w-3xl w-full mx-auto">
      <AccentCard accent="var(--color-danger)" as="div">
        <div className="flex items-start gap-3" data-testid="error-state">
          <StateIconRing accent="var(--color-danger)">
            <EmptyStateGlyph name="alert" />
          </StateIconRing>
          <div className="flex min-w-0 flex-1 flex-col gap-1 items-start">
            <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
              Something went wrong
            </p>
            <p role="alert" className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {technical ? "We couldn't load this. Try again in a moment." : message}
            </p>
            {technical ? (
              <details className="text-xs w-full" style={{ color: "var(--color-text-muted)" }}>
                <summary className="cursor-pointer font-semibold">Details</summary>
                <p className="mt-1 break-words" data-testid="error-details">
                  {message}
                </p>
              </details>
            ) : null}
            {onRetry ? (
              <Button size="sm" onClick={onRetry} className="mt-2">
                Try again
              </Button>
            ) : null}
          </div>
        </div>
      </AccentCard>
    </main>
  );
}

/** Full-page retry for a fetch-error ErrorState: re-runs auth restore and
 * every fetch the page makes on mount. */
export function reloadPage(): void {
  window.location.reload();
}
