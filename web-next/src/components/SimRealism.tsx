"use client";

import { useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import type { SimCtx } from "@/components/SimGameParts";
import { ToneBadge } from "@/components/ToneBadge";
import { CompactModule } from "@/components/ui/CompactModule";
import { Sheet } from "@/components/ui/Sheet";
import { api } from "@/lib/api";
import {
  SIM_REALISM_BANNER_DISMISS,
  SIM_REALISM_CANCEL_LABEL,
  SIM_REALISM_CONFIRM_LABEL,
  SIM_REALISM_CURRENT,
  SIM_REALISM_INTRO,
  SIM_REALISM_MENU_TITLE,
  SIM_REALISM_NOT_RETROACTIVE,
  SIM_REALISM_SHEET_DESCRIPTION,
  SIM_REALISM_SHEET_TITLE,
  SIM_REALISM_UNDO_NOTE,
  simRealismBanner,
  simRealismBannerKey,
  simRealismGroups,
  simRealismParts,
  simRealismPending,
  simRealismToast,
  simRealismWhen,
} from "@/lib/simRealism";
import { Presence } from "@/components/ui/Presence";

function readDismissed(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeDismissed(key: string) {
  try {
    window.localStorage.setItem(key, "1");
  } catch {
    // Storage can be blocked: the banner just shows again next visit.
  }
}

/**
 * The Realism update's confirm sheet: what changes (each rule with when it starts), the honest limit (past results stay), and
 * one confirm. The server appends one event to the game's log; nothing is rewritten.
 */
export function SimRealismSheet({ ctx, open, onClose }: { ctx: SimCtx; open: boolean; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const pending = simRealismPending(ctx.game);
  const groups = simRealismGroups(pending);

  async function confirm() {
    if (busy) return;
    setBusy(true);
    try {
      const body = await ctx.call(() => api.realismUpgradeSimGame(ctx.gameId));
      if (!body) return;
      ctx.setGame({ ...ctx.game, settings: body.settings ?? ctx.game.settings, rules: body.rules ?? ctx.game.rules });
      ctx.bump();
      ctx.notify(simRealismToast(body), "success");
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={SIM_REALISM_SHEET_TITLE}
      description={SIM_REALISM_SHEET_DESCRIPTION}
      testId="sim-realism-sheet"
      footer={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button size="sm" variant="secondary" onClick={onClose} disabled={busy}>{SIM_REALISM_CANCEL_LABEL}</Button>
          <Button size="sm" onClick={confirm} disabled={busy || pending.length === 0} data-testid="sim-realism-confirm">
            {busy ? "Updating..." : SIM_REALISM_CONFIRM_LABEL}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm">{SIM_REALISM_INTRO}</p>
        {groups.length === 0 ? (
          <p className="text-sm font-bold">{SIM_REALISM_CURRENT}</p>
        ) : (
          groups.map((g) => (
            <section key={g.boundary} className="flex flex-col gap-2" aria-label={g.when}>
              <ToneBadge label={g.when} color="var(--color-accent)" size="xs" />
              <ul className="flex flex-col gap-2" data-testid="sim-realism-list">
                {g.flags.map((f) => (
                  <li key={f.flag} className="flex flex-col gap-0.5" data-flag={f.flag}>
                    <span className="text-sm font-bold">{f.label}</span>
                    <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{f.body}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
        <p className="text-sm font-bold" data-testid="sim-realism-note">{SIM_REALISM_NOT_RETROACTIVE}</p>
        <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>{SIM_REALISM_UNDO_NOTE}</p>
      </div>
    </Sheet>
  );
}

/** The More / Game menu entry: the explanation, the status, and the button that opens the confirm sheet. */
export function SimRealismModule({ ctx }: { ctx: SimCtx }) {
  const [open, setOpen] = useState(false);
  const info = ctx.game.rules;
  if (!info) return null;
  const pending = simRealismPending(ctx.game);
  return (
    <>
      <CompactModule id="sim.menu.realism" testId="sim-realism-module" title={SIM_REALISM_MENU_TITLE} parts={simRealismParts(info)} tone={pending.length > 0 ? "accent" : "muted"} persist={false}>
        <p className="text-sm">{pending.length > 0 ? SIM_REALISM_INTRO : SIM_REALISM_CURRENT}</p>
        {pending.length > 0 ? (
          <ul className="flex flex-col gap-1 text-sm" aria-label="Rules an update turns on">
            {pending.map((f) => (
              <li key={f.flag}><span className="font-bold">{f.label}</span> <span style={{ color: "var(--color-text-tertiary)" }}>({simRealismWhen(f).toLowerCase()})</span></li>
            ))}
          </ul>
        ) : null}
        {info.scheduled.length > 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Starting next offseason: {info.scheduled.map((f) => f.label).join(", ")}.
          </p>
        ) : null}
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{SIM_REALISM_NOT_RETROACTIVE}</p>
        {pending.length > 0 ? <Button size="sm" variant="secondary" onClick={() => setOpen(true)} data-testid="sim-realism-open">Review and update</Button> : null}
      </CompactModule>
      {open ? <SimRealismSheet ctx={ctx} open={open} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

/** A compact, dismissible one-time banner on Home for an old save with at least one rule off. */
export function SimRealismBanner({ ctx }: { ctx: SimCtx }) {
  const key = simRealismBannerKey(ctx.gameId, ctx.game.rules);
  const [gone, setGone] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const dismissed = gone === key || (typeof window !== "undefined" && readDismissed(key));
  const banner = simRealismBanner(ctx.game, dismissed);
  return (
    <>
      {/* Dismissing collapses it away (Presence keeps the last banner on screen while it leaves). */}
      <Presence show={Boolean(banner)} variant="collapse">
      {banner ? (
      <AccentCard accent="var(--color-accent)" compact as="div" data-testid="sim-realism-banner">
        <div className="flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold">{banner.title}</p>
            <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{banner.body}</p>
          </div>
          <Button size="sm" onClick={() => setOpen(true)}>{banner.cta}</Button>
          <Button
            size="sm"
            variant="secondary"
            aria-label={SIM_REALISM_BANNER_DISMISS}
            onClick={() => {
              writeDismissed(key);
              setGone(key);
            }}
          >
            {SIM_REALISM_BANNER_DISMISS}
          </Button>
        </div>
      </AccentCard>
      ) : null}
      </Presence>
      {open ? <SimRealismSheet ctx={ctx} open={open} onClose={() => setOpen(false)} /> : null}
    </>
  );
}
