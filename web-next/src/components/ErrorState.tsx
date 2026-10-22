import { Button } from "@/components/Button";

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
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 px-4 text-center">
      <p role="alert" style={{ color: "var(--color-danger)" }}>
        {message}
      </p>
      {onRetry ? (
        <Button onClick={onRetry}>Try again</Button>
      ) : null}
    </main>
  );
}

/** Full-page retry for a fetch-error ErrorState: re-runs auth restore and
 * every fetch the page makes on mount. */
export function reloadPage(): void {
  window.location.reload();
}
