import Link from "next/link";

import { ToneBadge } from "@/components/ToneBadge";
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
      className={`glass-surface px-4 py-3 flex flex-col gap-0.5${copy.urgent ? " premium-glow-card" : ""}`}
      data-testid="deadline-card"
      style={{ borderLeft: `4px solid ${copy.urgent ? "var(--color-danger)" : "var(--color-accent)"}` }}
    >
      {state.weeksLeft !== null ? (
        <div className="flex items-center gap-2" data-testid="deadline-pips">
          <ToneBadge
            label={state.weeksLeft === 0 ? "Last call" : `${state.weeksLeft} wk${state.weeksLeft === 1 ? "" : "s"} left`}
            color={copy.urgent ? "var(--color-danger)" : "var(--color-accent)"}
            srLabel={`${state.weeksLeft} weeks left until the week ${state.deadlineWeek} trade deadline`}
          />
          <span className="flex gap-1 flex-1 max-w-[8rem]" aria-hidden="true">
            {Array.from({ length: 6 }, (_, i) => (
              <span
                key={i}
                className="flex-1 h-1.5"
                style={{
                  borderRadius: "var(--radius-pill)",
                  background: i < Math.max(1, 6 - state.weeksLeft!) ? (copy.urgent ? "var(--color-danger)" : "var(--color-accent)") : "var(--color-surface-muted)",
                }}
              />
            ))}
          </span>
          <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
            Wk {state.deadlineWeek}
          </span>
        </div>
      ) : null}
      <p className="m-0 text-sm font-bold">{copy.headline}</p>
      <p className="m-0 text-xs" style={{ color: "var(--color-text-secondary)" }}>
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
