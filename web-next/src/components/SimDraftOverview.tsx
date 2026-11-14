"use client";

import { useMemo, useState } from "react";

import { SimDraftGrid } from "@/components/SimDraftGrid";
import { Sheet } from "@/components/ui/Sheet";
import { CompactModule } from "@/components/ui/CompactModule";
import { positionColorVar } from "@/lib/playerPresentation";
import { simDraftMiniBoard, simDraftMiniWindow, simDraftPickChip, simDraftProgress, simDraftRecentPicks } from "@/lib/simDraft";
import type { SimDraftState, SimGamePlayer } from "@/lib/simGame";

/**
 * "Who has been drafted", always on the draft page (not behind a tab): a strip of the latest picks and a mini board
 * (rounds x teams of tiny position-coloured cells, your column outlined, the pick on the clock ringed). The mini
 * board shows the rounds around the clock; "Full board" opens the whole grid in a sheet. Mobile twin: SimDraftOverview.tsx.
 */
export function SimDraftOverview({ draft, teams, onOpen }: { draft: SimDraftState; teams: number; onOpen: (player: SimGamePlayer) => void }) {
  const [full, setFull] = useState(false);
  const recent = simDraftRecentPicks(draft.picks, 8);
  const progress = simDraftProgress(draft, teams);
  const mini = useMemo(() => simDraftMiniBoard(draft, teams), [draft, teams]);
  const win = simDraftMiniWindow(mini.rows, progress.round);
  const mine = (draft.picks ?? []).filter((p) => draft.teams?.find((t) => t.team_id === p.team_id)?.is_you).length;
  const last = recent[0];
  return (
    <div className="flex flex-col gap-2" data-testid="draft-overview">
      <ol className="flex gap-1.5 overflow-x-auto pb-0.5" aria-label="Recent picks" data-testid="recent-picks" style={{ scrollbarWidth: "none" }}>
        {recent.length === 0 ? (
          <li className="text-xs" style={{ color: "var(--color-text-muted)", minHeight: 32, display: "flex", alignItems: "center" }}>No picks yet. The first ones land here.</li>
        ) : (
          recent.map((pk) => {
            const colorVar = positionColorVar(pk.player.pos);
            return (
              <li key={pk.pick_no} className="shrink-0">
                <button
                  type="button"
                  onClick={() => onOpen(pk.player)}
                  className="whitespace-nowrap px-2 text-xs font-bold"
                  style={{ minHeight: 32, borderRadius: "var(--radius-control)", background: "var(--color-surface-muted)", borderBottom: `3px solid ${colorVar ? `var(${colorVar})` : "var(--color-border-strong)"}` }}
                  aria-label={`Pick ${pk.pick_no}: ${pk.player.name}, ${pk.player.pos}. Open player details`}
                >
                  {simDraftPickChip(pk)}
                </button>
              </li>
            );
          })
        )}
      </ol>
      <CompactModule
        id="draft.board"
        title="Draft board"
        tone="accent"
        defaultOpen
        parts={[
          { key: "n", text: `${progress.made}/${progress.total} picks`, strong: true },
          last ? { key: "last", text: `last ${simDraftPickChip(last)}` } : null,
          { key: "mine", text: `you ${mine}`, tone: "accent" },
        ]}
      >
        <div className="flex flex-col gap-1" data-testid="mini-board" role="img" aria-label={`Mini draft board, rounds ${win.from} to ${win.to}`}>
          {win.rows.map((row, i) => (
            <div key={win.from + i} className="flex items-center gap-1">
              <span className="shrink-0 text-[0.6875rem] font-extrabold tabular-nums" style={{ width: 22, color: "var(--color-text-muted)" }}>R{win.from + i}</span>
              <div className="grid min-w-0 flex-1 gap-[3px]" style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}>
                {row.map((cell) => {
                  const colorVar = cell.pos ? positionColorVar(cell.pos) : undefined;
                  return (
                    <span
                      key={cell.key}
                      title={cell.pickNo ? `#${cell.pickNo}${cell.pos ? ` ${cell.pos}` : ""}` : undefined}
                      style={{
                        height: 18,
                        borderRadius: 4,
                        background: colorVar ? `var(${colorVar})` : "transparent",
                        border: cell.clock ? "2px solid var(--color-action)" : cell.pos ? "none" : "1px dashed var(--color-border)",
                        outline: cell.you ? "1.5px solid var(--color-accent)" : undefined,
                        outlineOffset: 1,
                      }}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <button type="button" className="tap-link self-start text-xs font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }} onClick={() => setFull(true)}>
          Full board
        </button>
      </CompactModule>
      <Sheet open={full} onClose={() => setFull(false)} title="Full draft board" size="lg">
        <SimDraftGrid draft={draft} teams={teams} onOpen={(p) => { setFull(false); onOpen(p); }} />
      </Sheet>
    </div>
  );
}
