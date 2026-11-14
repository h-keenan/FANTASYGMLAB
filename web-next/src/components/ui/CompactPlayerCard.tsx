"use client";

import type { ReactNode } from "react";

import { PlayerName } from "@/components/PlayerName";
import { PositionBadge } from "@/components/PositionBadge";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import type { PlayerRef } from "@/lib/playerAnatomy";

/**
 * The compact player card used INSIDE other modules (trade give/get sides, bar rows, lineup slots): avatar, name +
 * position badge, a muted detail, one trailing value. It is the same anatomy as `PlayerAccordionRow` without the
 * accordion. Mobile twin: components/CompactPlayerCard.tsx.
 */
export function CompactPlayerCard({ player, detail, trailing, testId = "compact-player-card" }: { player: PlayerRef; detail?: string | null; trailing?: ReactNode; testId?: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2" style={{ minHeight: 40 }} data-testid={testId}>
      <PlayerAvatarSlot player={player} tier="dense" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex min-w-0 items-center gap-1.5">
          <PlayerName name={player.name} className="min-w-0 text-sm font-bold" style={{ color: "var(--color-text-primary)" }} />
          <PositionBadge position={player.position} />
        </span>
        {detail ? <span className="text-xs leading-4" style={{ color: "var(--color-text-muted)" }}>{detail}</span> : null}
      </span>
      {trailing ? <span className="shrink-0 text-sm font-extrabold tabular-nums">{trailing}</span> : null}
    </div>
  );
}
