"use client";

import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/Button";
import { Collapsible } from "@/components/Collapsible";
import { SimPlayerLine, SimSheet, SimStat, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { isSimRookieNoticeSeen, setSimRookieNoticeSeen } from "@/lib/simRookieNotice";
import {
  SIM_GENERATED_CLASS_LABEL,
  SIM_GENERATED_CLASS_NOTICE,
  simIsPick,
  simPickGroups,
  simPickLabelText,
  simPickSlotHint,
  simPickViaLine,
  simPlayerChips,
  type SimGamePlayer,
  type SimGameTone,
  type SimPickAsset,
  type SimPicksResponse,
  type SimTradeAsset,
} from "@/lib/simGame";

/**
 * A collapsible block for the dynasty screens: a thin adapter over the shared
 * Collapsible (the one the whole game uses), so the Team tab, the offseason
 * screens and the dynasty result open, close and remember their state the
 * same way as every other fold. Collapsed by default so a phone screen shows
 * the summary first.
 */
export function SimCollapse({
  title,
  summary,
  defaultOpen = false,
  tone = "muted",
  badge,
  children,
  testId,
}: {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  tone?: SimGameTone;
  badge?: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <Collapsible
      id={`dyn.${testId ?? title}`}
      testId={testId}
      accent={simToneColor(tone === "muted" ? "accent" : tone)}
      defaultOpen={defaultOpen}
      title={
        <span className="inline-flex items-center gap-2">
          {title}
          {badge}
        </span>
      }
      summary={summary ? <span className="text-xs font-normal normal-case" style={{ color: "var(--color-text-muted)" }}>{summary}</span> : undefined}
    >
      {children}
    </Collapsible>
  );
}

/** IR / TAXI / ROOKIE / OUT n wks chips for one roster row. */
export function SimPlayerChips({ player }: { player: Pick<SimGamePlayer, "squad" | "rookie" | "status" | "out_weeks"> }) {
  const chips = simPlayerChips(player);
  if (chips.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {chips.map((chip) => (
        <SimToneBadge key={chip.key} label={chip.label} tone={chip.tone} />
      ))}
    </span>
  );
}

/** One draft pick as a list row: "2027 Round 1 (early)", where it came from, and its value. */
export function SimPickLine({
  pick,
  trailing,
  selected = false,
  draftYear,
}: {
  pick: SimPickAsset;
  trailing?: ReactNode;
  selected?: boolean;
  draftYear?: number | null;
}) {
  const via = simPickViaLine(pick);
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2"
      data-testid="pick-row"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        background: selected ? "var(--color-accent-soft)" : undefined,
        minHeight: "var(--touch-target-min)",
      }}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2" style={{ minWidth: "min(100%, 12rem)" }}>
        <ToneBadge label={`R${pick.round}`} color="var(--color-accent)" size="xs" />
        <span className="flex min-w-0 flex-col leading-tight">
          <span className="text-sm font-bold">{simPickLabelText(pick)}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {[via, simPickSlotHint(pick, draftYear)].filter(Boolean).join(" · ")}
          </span>
        </span>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <SimStat label="Value" value={Math.round(pick.value)} />
        {trailing}
      </div>
    </div>
  );
}

/** A player or a pick, whichever the asset is (counter chips, inbox offers, verdicts). */
export function SimAssetLine({ asset, trailing, onOpen }: { asset: SimTradeAsset; trailing?: ReactNode; onOpen?: (player: SimGamePlayer) => void }) {
  if (simIsPick(asset)) return <SimPickLine pick={asset} trailing={trailing} />;
  return <SimPlayerLine player={asset} onOpen={onOpen} trailing={trailing ?? <SimStat label="Value" value={Math.round(asset.value)} />} />;
}

/** The picks of the game (every team's), or null until loaded; null for a redraft game. */
export function useSimPicks(ctx: Pick<SimCtx, "gameId" | "game" | "tick">): SimPicksResponse | null {
  const dynasty = ctx.game.settings.mode === "dynasty";
  const [picks, setPicks] = useState<SimPicksResponse | null>(null);
  useEffect(() => {
    if (!dynasty) return;
    let cancelled = false;
    api
      .getSimPicks(ctx.gameId)
      .then((body) => {
        if (!cancelled && !body.reason) setPicks(body);
      })
      .catch(() => {
        /* the picks group just stays empty */
      });
    return () => {
      cancelled = true;
    };
  }, [dynasty, ctx.gameId, ctx.tick]);
  return dynasty ? picks : null;
}

/**
 * The Picks group inside a trade asset picker: one team's picks grouped by
 * year then round. `selected` / `onToggle` are the same id-based state as the
 * players beside it (pick ids are plain strings).
 */
export function SimPickGroup({
  picks,
  selected,
  onToggle,
  side,
  draftYear,
  full = false,
}: {
  picks: SimPickAsset[];
  selected: string[];
  onToggle: (id: string) => void;
  side: "give" | "get";
  draftYear?: number | null;
  /** The side already holds its maximum; unselected picks are disabled. */
  full?: boolean;
}) {
  const groups = simPickGroups(picks);
  if (groups.length === 0) return null;
  return (
    <div className="flex flex-col" role="group" aria-label={side === "give" ? "Your picks" : "Their picks"} data-testid={`pick-group-${side}`}>
      <p className="pt-2 text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        {side === "give" ? "Your picks" : "Their picks"}
      </p>
      {groups.map((group) => (
        <div key={group.season} className="flex flex-col">
          <p className="pt-1 text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>
            {group.season}
          </p>
          {group.rounds.flatMap((r) => r.picks).map((pick) => {
            const on = selected.includes(pick.id);
            return (
              <SimPickLine
                key={pick.id}
                pick={pick}
                selected={on}
                draftYear={draftYear}
                trailing={
                  <Button
                    size="sm"
                    variant={on ? "primary" : "secondary"}
                    aria-pressed={on}
                    disabled={!on && full}
                    aria-label={`${side === "give" ? "Give" : "Get"} ${simPickLabelText(pick)}`}
                    onClick={() => onToggle(pick.id)}
                  >
                    {on ? (side === "give" ? "Giving" : "Getting") : side === "give" ? "Give" : "Get"}
                  </Button>
                }
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generated rookie class disclosure

/**
 * The small "Generated class - strong" chip with an info affordance. Tapping
 * it opens the notice (the parent owns the sheet). The hit area is a full
 * touch target even though the pill is small.
 */
export function SimGeneratedChip({ label = SIM_GENERATED_CLASS_LABEL, onInfo, inRow = false }: { label?: string; onInfo: () => void; inRow?: boolean }) {
  return (
    <button
      type="button"
      onClick={onInfo}
      className="inline-flex shrink-0 items-center"
      style={{ minHeight: "var(--touch-target-min)", marginBlock: inRow ? "-0.75rem" : undefined }}
      aria-label={`${label}. ${SIM_GENERATED_CLASS_NOTICE}`}
      data-testid="generated-chip"
    >
      <span
        className="inline-flex items-center gap-1 whitespace-nowrap px-2 py-0.5 text-[0.6875rem] font-extrabold uppercase"
        style={{
          borderRadius: "var(--radius-pill)",
          background: "color-mix(in srgb, var(--color-accent) 15%, transparent)",
          boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--color-accent) 40%, transparent)",
          color: "var(--color-accent)",
          letterSpacing: "var(--letter-spacing-badge)",
        }}
      >
        {label}
        <span aria-hidden="true" className="font-black normal-case">ⓘ</span>
      </span>
    </button>
  );
}

/** The notice sheet behind every Generated class chip and the first-time popup. */
export function SimGeneratedNoticeSheet({ onClose }: { onClose: () => void }) {
  return (
    <SimSheet title="Simulated rookie class" onClose={onClose}>
      <div className="flex flex-col gap-3 pb-2" data-testid="generated-notice">
        <p className="pr-8 text-lg font-extrabold">Simulated rookie class</p>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{SIM_GENERATED_CLASS_NOTICE}</p>
        <Button fullWidth onClick={onClose}>Got it</Button>
      </div>
    </SimSheet>
  );
}

/** Shows the notice once per game, the first time a rookie draft screen opens. */
export function SimRookieNoticeGate({ gameId }: { gameId: string }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    // Storage is read after mount (never during render) so the server and client markup agree.
    const timer = window.setTimeout(() => setOpen(!isSimRookieNoticeSeen(gameId)), 0);
    return () => window.clearTimeout(timer);
  }, [gameId]);
  if (!open) return null;
  return (
    <SimGeneratedNoticeSheet
      onClose={() => {
        setSimRookieNoticeSeen(gameId);
        setOpen(false);
      }}
    />
  );
}
