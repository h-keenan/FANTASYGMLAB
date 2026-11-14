"use client";

import { useEffect, useState, type ReactNode } from "react";

import { PillMorph } from "@/components/ui/PillMorph";
import { usePillState } from "@/lib/useBottomPillContext";
import { Button, ButtonLink } from "@/components/Button";
import { SimGlyph } from "@/components/SimGlyph";
import type { SimCtx } from "@/components/SimGameParts";
import { useSimAutoSet } from "@/components/useSimAutoSet";
import { api } from "@/lib/api";
import { simAdvanceLabel } from "@/lib/simGame";
import { simAdvanceState, simLineupIssues, type SimZeroStarter } from "@/lib/simLayout";

/**
 * The persistent bottom action bar for the in-season tabs: Advance week
 * ("Week 4 -> 5", disabled only when a cut is owed; an empty slot warns and
 * asks to confirm) and a secondary Auto-set pill. On phones it is an Advance-only floating glass pill
 * (.action-pill; Auto-set lives on Home "What to do this week") docked at the bottom of the game's in-flow
 * sticky `.bottom-stack` (one row: icon-only Sim to, the game orb, Advance; no position:fixed); sticky inside the page on desktop. Mobile twin: mobile/src/components/SimActionBar.tsx.
 */
export function SimActionBar({ ctx, paywalled, advancing, onAdvance, onSimTo, onTab, orb }: { ctx: SimCtx; paywalled: boolean; advancing: boolean; onAdvance: () => void; onSimTo?: () => void; onTab?: (tab: "team" | "players") => void; orb?: ReactNode }) {
  const pill = usePillState();
  const { gameId, game } = ctx;
  const [issues, setIssues] = useState<{ empty: string[]; zero: SimZeroStarter[] }>({ empty: [], zero: [] });
  const [confirming, setConfirming] = useState(false);
  const auto = useSimAutoSet(ctx);

  // Empty starter slots, so Advance can say "Fill 1 empty slot" from any tab.
  useEffect(() => {
    let cancelled = false;
    api
      .getSimLineup(gameId)
      .then((body) => {
        if (cancelled) return;
        setIssues(simLineupIssues(body.slots ?? [], body.warnings ?? []));
        setConfirming(false); // the lineup changed (e.g. the slot was filled): ask again
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, game]);

  const state = simAdvanceState(game, issues.empty, issues.zero);
  const tapAdvance = () => {
    if (state.confirm && !confirming) setConfirming(true);
    else {
      setConfirming(false);
      onAdvance();
    }
  };
  const reasonId = "sim-advance-reason";
  // The accessible name starts with the visible text (WCAG 2.5.3), then adds the plain-language detail.
  const advanceText = confirming ? "Advance anyway" : game.phase === "playoffs" ? "Play round" : `Advance ${state.label}`;
  return (
    <div className="sim-action-bar action-pill md:sticky md:inset-x-auto md:bottom-4 md:mx-auto md:flex md:w-full md:items-center md:justify-between md:gap-4 md:px-4 md:py-2" data-testid="sim-action-bar">
      {confirming && state.confirm && !paywalled ? (
        <div className="px-4 pt-1.5 text-center text-xs font-bold md:flex-1 md:p-0 md:text-left md:text-sm" role="alertdialog" aria-label="Confirm advance" data-testid="sim-advance-confirm" style={{ color: "var(--color-warning)" }}>
          <p>{state.confirm}</p>
          {onTab ? (
            <p className="mt-1 flex justify-center gap-3 md:justify-start">
              <button type="button" className="tap-link underline" onClick={() => { setConfirming(false); onTab("team"); }}>Fill from bench</button>
              <button type="button" className="tap-link underline" onClick={() => { setConfirming(false); onTab("players"); }}>Free agents</button>
              <button type="button" className="tap-link underline" onClick={() => setConfirming(false)}>Cancel</button>
            </p>
          ) : null}
        </div>
      ) : state.warning && !state.reason && !paywalled ? (
        <p className="max-md:hidden px-4 pt-1.5 text-center text-xs font-bold md:flex-1 md:p-0 md:text-left md:text-sm" style={{ color: "var(--color-warning)" }} role="status" data-testid="sim-advance-warning">
          {state.warning}
        </p>
      ) : null}
      {state.reason && !paywalled ? (
        <p id={reasonId} className="px-4 pt-1.5 text-center text-xs font-bold md:flex-1 md:p-0 md:text-left md:text-sm" style={{ color: "var(--color-warning)" }} role="status">
          {state.reason}
        </p>
      ) : confirming && state.confirm && !paywalled ? null : state.warning && !paywalled ? null : (
        <p className="hidden text-sm font-bold md:block md:flex-1" style={{ color: "var(--color-text-secondary)" }} data-testid="sim-action-bar-status">
          Week {game.week}{game.phase !== "playoffs" && game.settings?.regular_weeks ? ` of ${game.settings.regular_weeks}` : ""}
          <span aria-hidden="true"> &middot; </span>
          <span style={{ color: auto.optimal ? "var(--color-success)" : undefined }}>{auto.optimal ? "Lineup optimal" : "Lineup can improve"}</span>
        </p>
      )}
      <PillMorph context={pill.barPresent ? pill.ctx : null}>
      <div className="mx-auto flex max-w-3xl items-center gap-2 p-1 md:mx-0 md:max-w-none md:flex-none md:gap-2 md:p-0">
        {onSimTo && !paywalled ? (
          <Button variant="secondary" size="sm" className="min-w-0 shrink-0" disabled={advancing} onClick={onSimTo} aria-label="Sim to..." data-testid="sim-to-button">
            <SimGlyph name="matchup" size={16} />
            <span className="ml-1.5 max-md:hidden">Sim to...</span>
          </Button>
        ) : null}
        {orb}
        <Button className="max-md:hidden" variant="secondary" size="sm" loading={auto.busy} disabled={auto.optimal || paywalled} onClick={auto.run} aria-label={auto.optimal ? "Lineup is optimal" : "Auto-set best lineup"}>
          <SimGlyph name={auto.optimal ? "check" : "spark"} size={16} />
          <span className="ml-1.5">{auto.optimal ? "Optimal" : "Auto-set"}</span>
        </Button>
        {paywalled ? (
          <ButtonLink href="/premium" variant="premium" size="sm">Go Pro to continue</ButtonLink>
        ) : (
          <Button className="min-w-0 max-md:flex-1" loading={advancing} disabled={state.blocked} onClick={tapAdvance} aria-label={`${advanceText}. ${simAdvanceLabel(game)}`} aria-describedby={state.reason ? reasonId : undefined}>
            {advanceText}
          </Button>
        )}
      </div>
      </PillMorph>
    </div>
  );
}
