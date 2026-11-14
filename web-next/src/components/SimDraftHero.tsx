"use client";

import { useEffect, useState } from "react";

import { PositionBadge } from "@/components/PositionBadge";
import { simToneColor } from "@/components/SimGameParts";
import { api } from "@/lib/api";
import {
  simDraftBestByPosition,
  simDraftNeedPills,
  simDraftProgress,
  simDraftTeamEmblem,
} from "@/lib/simDraft";
import { simFmtValue, type SimDraftState, type SimGamePlayer, type SimPos, type SimSlot } from "@/lib/simGame";

function lastName(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 ? parts[parts.length - 1] : name;
}

const LABEL_STYLE = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" } as const;

/** Fixed-size team emblem: initials in a ring, accented for your own team. */
export function SimDraftEmblem({ name, you = false }: { name: string; you?: boolean }) {
  const color = you ? "var(--color-accent)" : "var(--color-text-secondary)";
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center text-[0.6875rem] font-extrabold"
      style={{
        width: 24,
        height: 24,
        borderRadius: "50%",
        color,
        background: `color-mix(in srgb, ${color} 14%, transparent)`,
        border: `var(--border-width-default) solid color-mix(in srgb, ${color} 45%, transparent)`,
      }}
    >
      {simDraftTeamEmblem(name)}
    </span>
  );
}

/**
 * The expanded on-the-clock body (inside the clock CompactModule): the progress bar, the best available player at
 * each position and your roster needs as colored pills. The status line, recent picks and mini board live elsewhere. Every block has a fixed
 * height so nothing shifts as picks land.
 */
export function SimDraftHero({
  gameId,
  draft,
  teams,
  slots,
  positions,
  tick,
  onOpen,
}: {
  gameId: string;
  draft: SimDraftState;
  teams: number;
  slots: SimSlot[];
  positions: SimPos[];
  tick: number;
  onOpen: (player: SimGamePlayer) => void;
}) {
  const progress = simDraftProgress(draft, teams);
  const onClock = Boolean(draft.on_the_clock?.is_you) && draft.status === "in_progress";
  const accent = onClock ? "var(--color-action)" : "var(--color-accent)";
  const needs = simDraftNeedPills(draft.your_roster, slots);
  const [best, setBest] = useState<Record<string, SimGamePlayer | null>>({});
  const pickCount = draft.picks?.length ?? 0;
  const done = draft.status === "complete";

  useEffect(() => {
    if (done) return;
    let cancelled = false;
    Promise.all(
      positions.map((pos) =>
        Promise.resolve(api.getSimGamePlayers(gameId, `pos=${pos}&status=available&sort=adp&page=1&page_size=1`))
          .then((body) => [pos, body?.items?.[0] ?? null] as const)
          .catch(() => [pos, null] as const),
      ),
    ).then((entries) => {
      if (!cancelled) setBest(Object.fromEntries(entries));
    });
    return () => {
      cancelled = true;
    };
    // positions is derived from settings and stable per game.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, tick, pickCount, done]);

  const strip = simDraftBestByPosition(
    positions.map((pos) => best[pos]).filter((p): p is SimGamePlayer => Boolean(p)),
    positions,
  );

  return (
    <div className="flex flex-col gap-3" data-testid="draft-hero">
      <div className="flex flex-col gap-1.5">
        <div
          role="progressbar"
          aria-label="Draft progress"
          aria-valuemin={0}
          aria-valuemax={progress.total}
          aria-valuenow={progress.made}
          className="h-2 overflow-hidden"
          style={{ background: "var(--color-surface-muted)", borderRadius: "var(--radius-pill)" }}
        >
          <div style={{ width: `${Math.round(progress.fraction * 100)}%`, height: "100%", background: accent, borderRadius: "var(--radius-pill)" }} />
        </div>
      </div>

      {!done ? (
        <div className="flex flex-col gap-1">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={LABEL_STYLE}>Best available</span>
          <ul className="flex gap-2 overflow-x-auto" style={{ minHeight: 44 }} aria-label="Best available by position">
            {strip.map(({ pos, player }) => (
              <li key={pos} className="shrink-0">
                <button
                  type="button"
                  disabled={!player}
                  onClick={() => player && onOpen(player)}
                  className="flex items-center gap-1.5 px-2 text-left"
                  style={{ height: 44, minWidth: 96, borderRadius: "var(--radius-control)", background: "var(--color-surface-muted)", opacity: player ? 1 : 0.5 }}
                  aria-label={player ? `Best available ${pos}: ${player.name}` : `No ${pos} left`}
                >
                  <PositionBadge position={pos} />
                  <span className="flex flex-col leading-tight">
                    <span className="text-xs font-bold">{player ? lastName(player.name) : "-"}</span>
                    <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>ADP {simFmtValue(player?.adp)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-col gap-1">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={LABEL_STYLE}>Your needs</span>
        <ul className="flex flex-wrap gap-1.5" aria-label="Roster needs">
          {needs.map((n) => (
            <li key={n.pos} className="flex items-center gap-1" title={n.starters === 0 ? `${n.pos}: no starter slot` : `${n.pos}: ${n.have} of ${n.starters} starters`}>
              <PositionBadge position={n.pos} label={`${n.pos} ${n.have}/${n.starters}`} />
              <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: "50%", background: simToneColor(n.tone) }} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
