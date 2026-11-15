"use client";

import { Sheet } from "@/components/ui/Sheet";
import { simParsePickId } from "@/lib/simGame";
import type { PickTapRef } from "@/components/ui/PlayerOpenContext";

/**
 * The pick detail every tapped pick opens inside Fantasy Sim (trade offers, the builder, the block, the team sheet):
 * what the pick is, which draft class, where it comes from and how its slot looks. Mobile twin:
 * components/SimPickSheet.tsx.
 */
export function SimPickSheet({ pick, onClose }: { pick: PickTapRef; onClose: () => void }) {
  const parsed = simParsePickId(pick.id);
  return (
    <Sheet open onClose={onClose} title={pick.label} description={parsed ? `Round ${parsed.round} pick, ${parsed.season} class` : "Draft pick"} size="sm" testId="sim-pick-sheet">
      <div className="flex flex-col gap-2 text-sm" data-testid="sim-pick-detail">
        {parsed ? (
          <p>
            <span className="font-bold">Round {parsed.round}</span> of the {parsed.season} draft.
          </p>
        ) : null}
        {pick.detail ? <p style={{ color: "var(--color-text-secondary)" }}>{pick.detail}</p> : null}
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          A pick turns into a rookie when its draft runs. Early picks are the valuable ones; the slot is set by the final standings of the season before.
        </p>
      </div>
    </Sheet>
  );
}
