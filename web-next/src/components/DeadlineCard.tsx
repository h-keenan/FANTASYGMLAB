import Link from "next/link";

import { deadlineCopy, deadlinePosture, deadlineState, type DeadlineWindow } from "@/lib/deadlineMode";

/**
 * Deadline countdown: "Deadline in 2 weeks: buy a starter" / "...sell aging
 * depth", from the league's real Sleeper deadline week and the effective team
 * strategy. Renders nothing unless a real deadline is still ahead (no
 * deadline, offseason and post-deadline leagues have nothing to count down;
 * callers own the closed-state copy). `maxWeeksLeft` hides it until the
 * deadline is near (Dashboard); the Trade Hub shows it whenever one is ahead.
 */
export function DeadlineCard({
  window,
  strategy,
  href,
  ctaLabel,
  maxWeeksLeft,
}: {
  window: DeadlineWindow | null | undefined;
  strategy: string | null | undefined;
  href?: string;
  ctaLabel?: string;
  /** Hide the card while the deadline is further away than this many weeks. */
  maxWeeksLeft?: number;
}) {
  const state = deadlineState(window);
  if (state.phase !== "open") return null;
  if (maxWeeksLeft !== undefined && (state.weeksLeft === null || state.weeksLeft > maxWeeksLeft)) return null;
  const copy = deadlineCopy(state, deadlinePosture(strategy));
  if (!copy) return null;
  return (
    <div
      className="glass-surface p-4 flex flex-col gap-1"
      data-testid="deadline-card"
      style={{ borderLeft: `4px solid ${copy.urgent ? "var(--color-danger)" : "var(--color-accent)"}` }}
    >
      <p className="m-0 text-sm font-bold">{copy.headline}</p>
      <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {copy.body}
      </p>
      {href && ctaLabel ? (
        <Link href={href} className="tap-link text-sm font-bold" style={{ color: "var(--color-accent)" }}>
          {ctaLabel} →
        </Link>
      ) : null}
    </div>
  );
}
