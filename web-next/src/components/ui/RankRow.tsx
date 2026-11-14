"use client";

import type { ReactNode } from "react";

import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import type { PlayerRef } from "@/lib/playerAnatomy";

/**
 * Bar row (waivers add row, standings, rankings): a mini bar showing the value (bid, points-for share) as a 0..1
 * `fraction` of the largest in the list, the player or team on the left, ONE trailing number. A `player` renders
 * through `CompactPlayerCard` (avatar included); a team passes `title` and `leading` (team avatar). Mobile twin:
 * components/RankRow.tsx.
 */
export function RankRow({
  player,
  title,
  leading,
  detail,
  fraction,
  trailing,
  barLabel,
  rank,
  onClick,
  testId = "rank-row",
}: {
  player?: PlayerRef;
  title?: string;
  leading?: ReactNode;
  detail?: string | null;
  fraction: number;
  trailing: ReactNode;
  barLabel?: string;
  rank?: number | null;
  onClick?: () => void;
  testId?: string;
}) {
  const pct = Math.round(Math.max(0, Math.min(1, fraction)) * 100);
  const body = (
    <div className="flex min-w-0 flex-col gap-1" data-testid={testId}>
      <div className="flex min-w-0 items-center gap-2">
        {rank != null ? <span className="w-5 shrink-0 text-xs font-extrabold tabular-nums" style={{ color: "var(--color-text-muted)" }}>{rank}</span> : null}
        <div className="min-w-0 flex-1">
          {player ? (
            <CompactPlayerCard player={player} detail={detail} trailing={trailing} />
          ) : (
            <div className="flex min-w-0 items-center gap-2" style={{ minHeight: 40 }}>
              {leading}
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="break-words text-sm font-bold">{title}</span>
                {detail ? <span className="text-xs leading-4" style={{ color: "var(--color-text-muted)" }}>{detail}</span> : null}
              </span>
              <span className="shrink-0 text-sm font-extrabold tabular-nums">{trailing}</span>
            </div>
          )}
        </div>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "rgba(255,255,255,0.1)" }} role="img" aria-label={barLabel ?? `${pct}% of the top`}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: "var(--color-accent-strong, var(--color-accent))" }} data-testid="rank-bar" />
      </div>
    </div>
  );
  return onClick ? (
    <button type="button" onClick={onClick} className="block w-full text-left" style={{ minHeight: "var(--touch-target-min)" }}>{body}</button>
  ) : (
    body
  );
}
