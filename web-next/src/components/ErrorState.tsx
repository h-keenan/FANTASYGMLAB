"use client";

import { useEffect } from "react";

import { Button } from "@/components/Button";
import { trackClientError } from "@/lib/analytics";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { FREE_LEAGUE_CAP_MESSAGE } from "@/lib/freeLeagueCap";

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
 * `onRetry` is optional only for messages that no retry can fix (e.g.
 * Player Compare's "No player selected to compare."). A page whose own
 * fetch effect has no retry token can pass `reloadPage`.
 */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const leagueLocked = message === FREE_LEAGUE_CAP_MESSAGE;
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
      <div className="glass-surface flex flex-col gap-1 items-start px-4 py-6" data-testid="error-state">
        <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
          Something went wrong
        </p>
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {message}
        </p>
        {onRetry ? (
          <Button size="sm" onClick={onRetry} className="mt-2">
            Try again
          </Button>
        ) : null}
      </div>
    </main>
  );
}

/** Full-page retry for a fetch-error ErrorState: re-runs auth restore and
 * every fetch the page makes on mount. */
export function reloadPage(): void {
  window.location.reload();
}
