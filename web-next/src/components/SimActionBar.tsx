"use client";

import { useEffect, useState } from "react";

import { Button, ButtonLink } from "@/components/Button";
import { SimGlyph } from "@/components/SimGlyph";
import type { SimCtx } from "@/components/SimGameParts";
import { useSimAutoSet } from "@/components/useSimAutoSet";
import { api } from "@/lib/api";
import { simAdvanceLabel } from "@/lib/simGame";
import { simAdvanceState } from "@/lib/simLayout";

/**
 * The persistent bottom action bar for the in-season tabs: Advance week
 * ("Week 4 -> 5", disabled with the reason when a slot is empty or a cut is
 * owed) and a secondary Auto-set pill. Fixed above the iOS safe area on phones
 * with a notch in the middle for the floating GM orb (which sits bottom
 * center); sticky inside the page on desktop. Page content gets matching
 * bottom padding from the caller. Mobile twin: mobile/src/components/SimActionBar.tsx.
 */
export function SimActionBar({ ctx, paywalled, advancing, onAdvance }: { ctx: SimCtx; paywalled: boolean; advancing: boolean; onAdvance: () => void }) {
  const { gameId, game } = ctx;
  const [emptySlots, setEmptySlots] = useState(0);
  const auto = useSimAutoSet(ctx);

  // Empty starter slots, so Advance can say "Fill 1 empty slot" from any tab.
  useEffect(() => {
    let cancelled = false;
    api
      .getSimLineup(gameId)
      .then((body) => {
        if (!cancelled) setEmptySlots((body.slots ?? []).filter((s) => !s.player).length);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, game.week]);

  const state = simAdvanceState(game, emptySlots);
  const reasonId = "sim-advance-reason";
  return (
    <div className="sim-action-bar fixed inset-x-0 bottom-0 z-30 md:sticky md:inset-x-auto md:bottom-4 md:mx-auto md:flex md:w-full md:items-center md:justify-between md:gap-4 md:px-4 md:py-2" data-testid="sim-action-bar">
      {state.reason && !paywalled ? (
        <p id={reasonId} className="px-4 pt-1.5 text-center text-xs font-bold md:flex-1 md:p-0 md:text-left md:text-sm" style={{ color: "var(--color-warning)" }} role="status">
          {state.reason}
        </p>
      ) : (
        <p className="hidden text-sm font-bold md:block md:flex-1" style={{ color: "var(--color-text-secondary)" }} data-testid="sim-action-bar-status">
          Week {game.week}{game.phase !== "playoffs" && game.settings?.regular_weeks ? ` of ${game.settings.regular_weeks}` : ""}
          <span aria-hidden="true"> &middot; </span>
          <span style={{ color: auto.optimal ? "var(--color-success)" : undefined }}>{auto.optimal ? "Lineup optimal" : "Lineup can improve"}</span>
        </p>
      )}
      <div className="mx-auto grid max-w-3xl grid-cols-[1fr_4.25rem_1fr] items-center gap-2 px-4 py-2 md:mx-0 md:flex md:max-w-none md:flex-none md:gap-2 md:p-0">
        <Button variant="secondary" size="sm" loading={auto.busy} disabled={auto.optimal || paywalled} onClick={auto.run} aria-label={auto.optimal ? "Lineup is optimal" : "Auto-set best lineup"}>
          <SimGlyph name={auto.optimal ? "check" : "spark"} size={16} />
          <span className="ml-1.5">{auto.optimal ? "Optimal" : "Auto-set"}</span>
        </Button>
        <span aria-hidden="true" className="md:hidden" />
        {paywalled ? (
          <ButtonLink href="/premium" variant="premium" size="sm">Go Pro to continue</ButtonLink>
        ) : (
          <Button className="whitespace-nowrap" loading={advancing} disabled={state.blocked} onClick={onAdvance} aria-label={simAdvanceLabel(game)} aria-describedby={state.reason ? reasonId : undefined}>
            {game.phase === "playoffs" ? "Play round" : `Advance ${state.label}`}
          </Button>
        )}
      </div>
    </div>
  );
}
