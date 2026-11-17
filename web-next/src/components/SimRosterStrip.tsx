"use client";

import { useState } from "react";

import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { Collapse } from "@/components/ui/Presence";
import { PositionBadge } from "@/components/PositionBadge";
import { positionColorVar } from "@/lib/playerPresentation";
import { simDraftRosterStrip } from "@/lib/simDraft";
import { simHeadshotId, type SimGamePlayer, type SimSlot } from "@/lib/simGame";

const AVATAR = 28; // the dense avatar tier

/**
 * "Your roster" inside the draft clock: the league's starting slots in order, filled slots show the drafted player (tap
 * opens him), empty strict slots are dashed outlines in the warning colour (the same holes the header's "need RB/TE"
 * names, one source: `simDraftRosterStrip`), plus "Bench n/m". Tapping the strip expands the full roster grouped by
 * position; collapsed by default (compact, tap to expand). Used by the startup and rookie drafts. Mobile twin: SimRosterStrip.tsx.
 */
export function SimRosterStrip({ roster, slots, rosterLimit, bench, onOpen }: { roster: readonly SimGamePlayer[]; slots: readonly SimSlot[]; rosterLimit: number; bench?: number | null; onOpen: (player: SimGamePlayer) => void }) {
  const [open, setOpen] = useState(false);
  const strip = simDraftRosterStrip(roster, slots, rosterLimit, bench);
  const needs = [...new Set(strip.slots.filter((c) => c.need).map((c) => c.label))];
  if (strip.slots.length === 0) return null;
  const toggle = () => setOpen((v) => !v);
  return (
    <div className="flex flex-col gap-1" data-testid="roster-strip">
      <button type="button" onClick={toggle} aria-expanded={open} className="flex items-center gap-2" style={{ minHeight: "var(--touch-target-min)", color: "inherit" }} data-testid="roster-strip-toggle">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>Your roster</span>
        <span className="flex flex-1 flex-wrap items-center gap-1" data-testid="roster-strip-needs">
          {needs.map((pos) => (
            <span key={pos} className="px-1.5 text-[0.6875rem] font-extrabold" style={{ color: "var(--color-warning)", borderRadius: "var(--radius-pill)", border: "1px solid color-mix(in srgb, var(--color-warning) 45%, transparent)" }}>
              Need {pos}
            </span>
          ))}
        </span>
        <span className="text-xs font-bold tabular-nums" style={{ color: "var(--color-text-muted)" }} data-testid="roster-strip-bench">
          Bench {strip.bench.have}/{strip.bench.max} {open ? "▴" : "▾"}
        </span>
      </button>
      {/* ONE fixed grid: every slot is the same size with the label at the same height, filled or empty, in lineup order on one row. */}
      <ul className="grid gap-x-1" style={{ gridTemplateColumns: `repeat(${strip.slots.length}, minmax(0, 1fr))` }} aria-label="Starting lineup slots" data-testid="roster-strip-slots">
        {strip.slots.map((cell) => (
          <li key={cell.key} className="flex flex-col items-center gap-0.5" data-testid={cell.player ? "roster-slot-filled" : "roster-slot-empty"} data-need={cell.need ? "true" : undefined}>
            {cell.player ? (
              <PlayerAvatarSlot player={{ id: cell.player.id, name: cell.player.name, position: cell.player.pos, team: cell.player.team ?? null, headshotId: simHeadshotId(cell.player) }} tier="dense" onOpen={() => onOpen(cell.player!)} />
            ) : (
              <button type="button" onClick={toggle} aria-label={`${cell.label} slot empty${cell.need ? ", you need one" : ""}`} className="flex items-center justify-center text-[0.6875rem] font-extrabold" style={{ width: AVATAR, height: AVATAR, borderRadius: "50%", border: "1.5px dashed var(--color-warning)", color: "var(--color-warning)" }}>
                +
              </button>
            )}
            <span className="text-[0.6875rem] font-extrabold" style={{ color: cell.player ? `var(${positionColorVar(cell.player.pos)})` : "var(--color-warning)" }} aria-label={cell.player ? `${cell.label}: ${cell.player.name}, ${cell.player.pos}` : undefined}>
              {cell.label}
            </span>
          </li>
        ))}
      </ul>
      <Collapse open={open} testId="roster-strip-full">
        <div className="flex flex-col gap-2">
          {strip.groups.map((g) => (
            <section key={g.pos} aria-label={`${g.pos} players`} className="flex flex-col gap-1">
              <p className="text-xs font-extrabold" style={{ color: g.starters > 0 && g.have < g.starters ? "var(--color-warning)" : "var(--color-text-muted)" }}>
                {g.pos} {g.have}/{g.starters}
              </p>
              {g.players.length === 0 ? (
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>None yet</p>
              ) : (
                g.players.map((pl) => (
                  <div key={pl.id} className="flex items-center gap-2" data-testid="roster-strip-player">
                    <PlayerAvatarSlot player={{ id: pl.id, name: pl.name, position: pl.pos, team: pl.team ?? null, headshotId: simHeadshotId(pl) }} tier="dense" onOpen={() => onOpen(pl)} />
                    <span className="min-w-0 flex-1 break-words text-sm font-bold">{pl.name}</span>
                    <PositionBadge position={pl.pos} />
                  </div>
                ))
              )}
            </section>
          ))}
        </div>
      </Collapse>
    </div>
  );
}
