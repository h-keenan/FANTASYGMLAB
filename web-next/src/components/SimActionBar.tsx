"use client";

import { useEffect, useState } from "react";

import { Button, ButtonLink } from "@/components/Button";
import { SimGlyph } from "@/components/SimGlyph";
import type { SimCtx } from "@/components/SimGameParts";
import { useSimAutoSet } from "@/components/useSimAutoSet";
import { api } from "@/lib/api";
import { simAdvanceLabel } from "@/lib/simGame";
import { simAdvanceState, simEmptySlotLabels } from "@/lib/simLayout";

/**
 * The persistent bottom action bar for the in-season tabs: Advance week
 * ("Week 4 -> 5", disabled only when a cut is owed; an empty slot warns and
 * asks to confirm) and a secondary Auto-set pill. Fixed above the iOS safe area on phones
 * with a notch in the middle for the floating GM orb (which sits bottom
 * center); sticky inside the page on desktop. Page content gets matching
 * bottom padding from the caller. Mobile twin: mobile/src/components/SimActionBar.tsx.
 */
export function SimActionBar({ ctx, paywalled, advancing, onAdvance, onTab }: { ctx: SimCtx; paywalled: boolean; advancing: boolean; onAdvance: () => void; onTab?: (tab: "team" | "players") => void }) {
  const { gameId, game } = ctx;
  const [emptySlots, setEmptySlots] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const auto = useSimAutoSet(ctx);

  // Empty starter slots, so Advance can say "Fill 1 empty slot" from any tab.
  useEffect(() => {
    let cancelled = false;
    api
      .getSimLineup(gameId)
      .then((body) => {
        if (cancelled) return;
        setEmptySlots(simEmptySlotLabels(body.slots ?? []));
        setConfirming(false); // the lineup changed (e.g. the slot was filled): ask again
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, game.week]);

  const state = simAdvanceState(game, emptySlots);
  const tapAdvance = () => {
    if (state.confirm && !confirming) setConfirming(true);
    else {
      setConfirming(false);
      onAdvance();
    }
  };
  const reasonId = "sim-advance-reason";
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-30 md:sticky md:inset-x-auto"
      style={{
        background: "color-mix(in srgb, var(--color-bg) 92%, transparent)",
        backdropFilter: "blur(10px)",
        borderTop: "var(--border-width-default) solid var(--color-border)",
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
      data-testid="sim-action-bar"
    >
      {confirming && state.confirm && !paywalled ? (
        <div className="px-4 pt-1.5 text-center text-xs font-bold" role="alertdialog" aria-label="Confirm advance" data-testid="sim-advance-confirm" style={{ color: "var(--color-warning)" }}>
          <p>{state.confirm}</p>
          {onTab ? (
            <p className="mt-1 flex justify-center gap-3">
              <button type="button" className="tap-link underline" onClick={() => { setConfirming(false); onTab("team"); }}>Fill from bench</button>
              <button type="button" className="tap-link underline" onClick={() => { setConfirming(false); onTab("players"); }}>Free agents</button>
              <button type="button" className="tap-link underline" onClick={() => setConfirming(false)}>Cancel</button>
            </p>
          ) : null}
        </div>
      ) : state.warning && !state.reason && !paywalled ? (
        <p className="px-4 pt-1.5 text-center text-xs font-bold" style={{ color: "var(--color-warning)" }} role="status" data-testid="sim-advance-warning">
          {state.warning}
        </p>
      ) : null}
      {state.reason && !paywalled ? (
        <p id={reasonId} className="px-4 pt-1.5 text-center text-xs font-bold" style={{ color: "var(--color-warning)" }} role="status">
          {state.reason}
        </p>
      ) : null}
      <div className="mx-auto grid max-w-3xl grid-cols-[1fr_4.25rem_1fr] items-center gap-2 px-4 py-2 md:grid-cols-[auto_1fr_auto]">
        <Button variant="secondary" size="sm" loading={auto.busy} disabled={auto.optimal || paywalled} onClick={auto.run} aria-label={auto.optimal ? "Lineup is optimal" : "Auto-set best lineup"}>
          <SimGlyph name={auto.optimal ? "check" : "spark"} size={16} />
          <span className="ml-1.5">{auto.optimal ? "Optimal" : "Auto-set"}</span>
        </Button>
        <span aria-hidden="true" />
        {paywalled ? (
          <ButtonLink href="/premium" variant="premium" size="sm">Go Pro to continue</ButtonLink>
        ) : (
          <Button className="whitespace-nowrap" loading={advancing} disabled={state.blocked} onClick={tapAdvance} aria-label={simAdvanceLabel(game)} aria-describedby={state.reason ? reasonId : undefined}>
            {confirming ? "Advance anyway" : game.phase === "playoffs" ? "Play round" : `Advance ${state.label}`}
          </Button>
        )}
      </div>
    </div>
  );
}
