"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { PillMorph } from "@/components/ui/PillMorph";
import { simFooterTabs, simPillPlan, type PillContext } from "@/lib/bottomNav";
import type { SimTab } from "@/lib/simGameFlow";
import { usePillState } from "@/lib/useBottomPillContext";
import { Button } from "@/components/Button";
import type { SimCtx } from "@/components/SimGameParts";
import { api } from "@/lib/api";
import { simTabAfterStageAction, type SimStageAction } from "@/lib/simScroll";
import { simOffseasonCta, simOffseasonStageLabel, simSeasonLabel, type SimOffseason, type SimOffseasonResponse } from "@/lib/simGame";

/**
 * The one persistent primary action for every offseason tab (Offseason, Team,
 * Trades, League): Start rookie draft, Auto-draft the rest (asks first), then
 * Start season N (saves from before the soft roster limit show "Finish cut-down", disabled with the reason, until the roster is legal;
 * newer saves only show a compact over-the-limit note: you can start the season over the limit, you just cannot add players). A floating glass pill above the bottom tab bar on phones (no orb), sticky on desktop, same frame as SimActionBar. It reads the offseason
 * itself, so any tab can mount it. Mobile twin: mobile/src/components/SimOffseasonBar.tsx.
 */
export function SimOffseasonBar({ ctx, onTab, orb, tab }: { ctx: SimCtx; onTab?: (tab: SimTab) => void; orb?: ReactNode; /** The lit page (Offseason / Team / ...): the phone pill lights its tab. */ tab?: string }) {
  const pill = usePillState();
  const { gameId, call } = ctx;
  const [off, setOff] = useState<SimOffseason | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmAuto, setConfirmAuto] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimOffseason(gameId, "")
      .then((body) => {
        if (!cancelled && body.offseason) setOff(body.offseason);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick]);

  const run = useCallback(
    async (fn: () => Promise<SimOffseasonResponse>, message?: (body: SimOffseasonResponse) => string, action?: SimStageAction) => {
      setBusy(true);
      const body = await call(fn);
      setBusy(false);
      if (body) {
        if (body.offseason) setOff(body.offseason);
        if (body.game) ctx.setGame(body.game);
        ctx.bump();
        if (action) onTab?.(simTabAfterStageAction(action));
        const text = message?.(body);
        if (text) ctx.notify(text, "success");
      }
    },
    [call, ctx, onTab],
  );

  if (!off) return null;
  const cta = simOffseasonCta(off);
  const reasonId = "sim-offseason-reason";

  function press() {
    if (!off) return;
    if (off.stage === "review") {
      void run(() => api.startSimRookieDraft(gameId), (b) => ((b.made?.length ?? 0) > 0 ? `${b.made?.length} AI picks made. You are up.` : ""), "start_rookie_draft");
    } else if (off.stage === "rookie_draft") {
      setConfirmAuto(true);
    } else {
      void run(async () => (await api.startSimSeason(gameId)) as SimOffseasonResponse, () => `${off.season_label || simSeasonLabel(off.season_no + 1, off.year)} is on.`, "start_season");
    }
  }

  // Phones (concept A): orb | Offseason / Team (/ Trades) | the stage chip. A long stage label ("Start next season") yields a tab.
  const phoneSegment: PillContext | null = pill.barPresent
    ? {
        id: "sim-offseason",
        label: "Fantasy Sim pages",
        tabs: simFooterTabs({ offseason: true, chipLabel: cta.label }),
        activeKey: tab ?? "home",
        onSelect: (key) => onTab?.(key as SimTab),
        primary: { key: "stage", label: cta.label, busy: busy && !confirmAuto, disabled: Boolean(cta.blocked) || confirmAuto, onPress: press },
      }
    : null;

  return (
    <div
      className="sim-action-bar action-pill md:sticky md:inset-x-auto md:bottom-4 md:mx-auto md:w-full"
      data-testid="sim-offseason-bar"
    >
      {off.stage === "rookie_draft" && confirmAuto ? (
        <div className="mx-auto flex max-w-3xl flex-col gap-2 px-4 pt-2">
          <p className="text-sm" role="alert">Auto-draft makes every one of your remaining picks for you, best available by your needs.</p>
          <div className="flex gap-2">
            <Button size="sm" loading={busy} onClick={() => { setConfirmAuto(false); void run(() => api.autoSimRookieDraft(gameId), () => "The rookie draft is done.", "auto_draft"); }}>
              Auto-draft the rest
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirmAuto(false)}>Keep drafting</Button>
          </div>
        </div>
      ) : null}
      {cta.note ? (
        <p className="px-4 pt-1.5 text-center text-xs font-bold" style={{ color: "var(--color-warning)" }} role="status" data-testid="offseason-over-note">{cta.note}</p>
      ) : null}
      {cta.blocked ? (
        <p id={reasonId} className="px-4 pt-1.5 text-center text-xs font-bold" style={{ color: "var(--color-warning)" }} role="status">{cta.blocked}</p>
      ) : null}
      <PillMorph segment={phoneSegment ?? simPillPlan({ context: pill.barPresent ? pill.ctx : null, simToAvailable: false }).segment} orb={orb}>
      <div className="mx-auto flex max-w-3xl items-center gap-2 max-md:p-0 md:p-1 md:grid md:grid-cols-[1fr_auto]">
        <span className="min-w-0 text-xs font-bold max-md:hidden" style={{ color: "var(--color-text-muted)" }}>
          {simOffseasonStageLabel(off.stage)}
        </span>
        <Button className={`min-w-0 whitespace-nowrap max-md:flex-1 ${cta.blocked ? "ring-1 ring-[var(--color-border-strong)]" : ""}`} fullWidth loading={busy && !confirmAuto} disabled={Boolean(cta.blocked) || confirmAuto} onClick={press} aria-describedby={cta.blocked ? reasonId : undefined}>
          {cta.label}
        </Button>
      </div>
      </PillMorph>
    </div>
  );
}
