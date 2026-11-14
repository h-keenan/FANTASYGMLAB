"use client";

import { useMemo } from "react";

import { EmptyState } from "@/components/EmptyState";
import { SimDraftEmblem } from "@/components/SimDraftHero";
import { positionColorVar } from "@/lib/playerPresentation";
import { simDraftBoardGrid } from "@/lib/simDraft";
import type { SimDraftState, SimGamePlayer } from "@/lib/simGame";
import { PlayerName } from "@/components/PlayerName";

const COL = 76;

/**
 * Rounds x teams draft board. Picks are tinted by position, your column is
 * outlined, the pick on the clock pulses an accent ring. The grid scrolls
 * horizontally inside its own box; the page never does.
 */
export function SimDraftGrid({ draft, teams, onOpen }: { draft: SimDraftState; teams: number; onOpen: (player: SimGamePlayer) => void }) {
  const grid = useMemo(() => simDraftBoardGrid(draft, teams), [draft, teams]);
  if (grid.teams.length === 0) return <EmptyState title="No board yet" subtitle="The draft grid shows up once teams are set." />;
  return (
    <section className="flex flex-col gap-2" aria-label="Draft board grid">
      <div className="overflow-auto" style={{ maxHeight: "70vh", borderRadius: "var(--radius-control)", border: "var(--border-width-default) solid var(--color-border)" }} data-testid="draft-grid-scroll">
        <table className="border-collapse" style={{ minWidth: 40 + grid.teams.length * COL }}>
          <thead>
            <tr>
              <th className="sticky left-0 top-0 z-20" style={{ width: 40, background: "var(--color-surface)" }} aria-label="Round" />
              {grid.teams.map((t) => (
                <th key={t.team_id} className="sticky top-0 z-10 p-1" style={{ width: COL, background: "var(--color-surface)", borderBottom: t.is_you ? "3px solid var(--color-accent)" : "var(--border-width-default) solid var(--color-border)" }}>
                  <span className="flex flex-col items-center gap-0.5">
                    <SimDraftEmblem name={t.name} you={t.is_you} />
                    <span className="max-w-full truncate text-[0.6875rem] font-bold" style={{ color: t.is_you ? "var(--color-accent)" : "var(--color-text-muted)", width: COL - 8 }}>{t.is_you ? "You" : t.name}</span>
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.rows.map((row, i) => (
              <tr key={i}>
                <th scope="row" className="sticky left-0 z-10 text-[0.6875rem] font-extrabold" style={{ background: "var(--color-surface)", color: "var(--color-text-muted)" }}>R{i + 1}</th>
                {row.map((cell, c) => {
                  const you = grid.teams[c].is_you;
                  const colorVar = cell.pick ? positionColorVar(cell.pick.player.pos) : undefined;
                  const clock = !cell.pick && cell.pickNo === draft.pick_no && draft.status === "in_progress";
                  const tint = colorVar ? `var(${colorVar})` : null;
                  return (
                    <td key={cell.teamId} className="p-0.5" style={{ width: COL, background: you ? "var(--color-accent-soft)" : undefined }}>
                      {cell.pick ? (
                        <button
                          type="button"
                          onClick={() => onOpen(cell.pick!.player)}
                          className="flex w-full flex-col items-start justify-center px-1 text-left"
                          style={{
                            height: 44,
                            borderRadius: 8,
                            background: tint ? `color-mix(in srgb, ${tint} 22%, transparent)` : "var(--color-surface-muted)",
                            borderLeft: `3px solid ${tint ?? "var(--color-border-strong)"}`,
                          }}
                          aria-label={`Pick ${cell.pick.pick_no}: ${cell.pick.player.name}, ${cell.pick.player.pos}`}
                        >
                          <PlayerName name={cell.pick.player.name} className="w-full text-[0.6875rem] font-bold" />
                          <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>{cell.pick.player.pos} · #{cell.pick.pick_no}</span>
                        </button>
                      ) : (
                        <span
                          className="flex items-center justify-center text-[0.6875rem] tabular-nums"
                          style={{
                            height: 44,
                            borderRadius: 8,
                            color: clock ? "var(--color-action)" : "var(--color-text-muted)",
                            border: clock ? "2px solid var(--color-action)" : "var(--border-width-default) dashed var(--color-border)",
                          }}
                        >
                          {cell.pickNo ?? ""}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
