"use client";

import type { ReactNode } from "react";

import { PlayerName } from "@/components/PlayerName";
import { PositionBadge } from "@/components/PositionBadge";
import { PlayerTap } from "@/components/ui/PlayerOpenContext";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import type { PlayerRef } from "@/lib/playerAnatomy";

/**
 * The compact player card used INSIDE other modules (trade give/get sides, bar rows, lineup slots): avatar, name +
 * position badge, a muted detail, one trailing value. It is the same anatomy as `PlayerAccordionRow` without the
 * accordion. The whole card is the tap target and opens the quick view by default (role button, 44px, press feedback);
 * pass `onOpen` to open something else or `nonInteractive="reason"` for a card inside a control that already acts
 * (a picker row that selects). A `trailing` that is itself a control needs `nonInteractive` on the card and its own
 * tap target beside it. Mobile twin: components/CompactPlayerCard.tsx.
 */
export function CompactPlayerCard({ player, detail, trailing, testId = "compact-player-card", onOpen, nonInteractive }: { player: PlayerRef; detail?: string | null; trailing?: ReactNode; testId?: string; onOpen?: () => void; nonInteractive?: string }) {
  const card = (
    <div className="flex min-w-0 items-center gap-2" style={{ minHeight: 40 }} data-testid={testId}>
      <PlayerAvatarSlot player={player} tier="dense" nonInteractive="the whole card is the tap target" />
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
  return (
    <PlayerTap player={player} onOpen={onOpen} nonInteractive={nonInteractive}>
      {card}
    </PlayerTap>
  );
}
