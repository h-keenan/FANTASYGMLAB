"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import type { SimCtx } from "@/components/SimGameParts";
import { api } from "@/lib/api";
import { simTabAfterStageAction, type SimStageAction } from "@/lib/simScroll";
import { simOffseasonCta, simOffseasonStageLabel, type SimOffseason, type SimOffseasonResponse } from "@/lib/simGame";

/**
 * The one persistent primary action for every offseason tab (Offseason, Team,
 * Trades, League): Start rookie draft, Auto-draft the rest (asks first), then
 * "Finish cut-down" (disabled, with the reason) until the roster is legal and
 * Start season N. Fixed above the safe area on phones with a notch for the GM
 * orb, sticky on desktop, same frame as SimActionBar. It reads the offseason
 * itself, so any tab can mount it. Mobile twin: mobile/src/components/SimOffseasonBar.tsx.
 */
export function SimOffseasonBar({ ctx, onTab }: { ctx: SimCtx; onTab?: (tab: "home") => void }) {
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
      void run(async () => (await api.startSimSeason(gameId)) as SimOffseasonResponse, () => `Season ${off.season_no + 1} is on.`, "start_season");
    }
  }

  return (
    <div
      className="sticky bottom-0 z-30 mt-auto -mx-4 -mb-[4.5rem] md:static md:mx-0 md:mb-0"
      style={{
        background: "color-mix(in srgb, var(--color-bg) 92%, transparent)",
        backdropFilter: "blur(10px)",
        borderTop: "var(--border-width-default) solid var(--color-border)",
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
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
      {cta.blocked ? (
        <p id={reasonId} className="px-4 pt-1.5 text-center text-xs font-bold" style={{ color: "var(--color-warning)" }} role="status">{cta.blocked}</p>
      ) : null}
      <div className="mx-auto grid max-w-3xl grid-cols-[1fr_4.25rem_1.4fr] items-center gap-2 px-4 py-2 md:grid-cols-[1fr_auto]">
        <span className="min-w-0 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>
          {simOffseasonStageLabel(off.stage)}
        </span>
        <span aria-hidden="true" className="md:hidden" />
        <Button className={`whitespace-nowrap ${cta.blocked ? "ring-1 ring-[var(--color-border-strong)]" : ""}`} fullWidth loading={busy && !confirmAuto} disabled={Boolean(cta.blocked) || confirmAuto} onClick={press} aria-describedby={cta.blocked ? reasonId : undefined}>
          {cta.label}
        </Button>
      </div>
    </div>
  );
}
