"use client";

import { useEffect, useState, type ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { SimPlayerLine, SimStat, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import {
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
 * A collapsible block: a full-width header button (title, one summary line,
 * chevron) over a body. Collapsed by default so a phone screen shows the
 * summary first. Used by the Team tab, the offseason screens and the dynasty
 * result, so they all open and close the same way.
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
  const [open, setOpen] = useState(defaultOpen);
  return (
    <AccentCard accent={simToneColor(tone === "muted" ? "accent" : tone)} compact as="section" data-testid={testId}>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 text-left"
        style={{ minHeight: "var(--touch-target-min)" }}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="flex min-w-0 flex-col">
          <span className="flex items-center gap-2 text-sm font-extrabold">
            {title}
            {badge}
          </span>
          {summary ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {summary}
            </span>
          ) : null}
        </span>
        <svg
          aria-hidden="true"
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ flexShrink: 0, transform: open ? "rotate(180deg)" : undefined, color: "var(--color-text-muted)" }}
        >
          <path d="M4 6l4 4 4-4" />
        </svg>
      </button>
      {open ? <div className="flex flex-col gap-1 pt-1">{children}</div> : null}
    </AccentCard>
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
