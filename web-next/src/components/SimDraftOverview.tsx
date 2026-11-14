"use client";

import { useState } from "react";

import { SimDraftGrid } from "@/components/SimDraftGrid";
import { Sheet } from "@/components/ui/Sheet";
import { CompactModule } from "@/components/ui/CompactModule";
import { positionColorVar } from "@/lib/playerPresentation";
import { simDraftMiniBoard, simDraftMiniWindow, simDraftPickChip, simDraftProgress, simDraftRecentPicks, simRookieMiniBoard, simRookieRecentChips, type SimMiniCell } from "@/lib/simDraft";
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
  const mini = simDraftMiniBoard(draft, teams);
  const win = simDraftMiniWindow(mini.rows, progress.round);
  const mine = (draft.picks ?? []).filter((p) => draft.teams?.find((t) => t.team_id === p.team_id)?.is_you).length;
  const last = recent[0];
  return (
    <div className="flex flex-col gap-2" data-testid="draft-overview">
      <SimRecentStrip
        chips={recent.map((pk) => ({ key: String(pk.pick_no), label: simDraftPickChip(pk), pos: pk.player.pos, aria: `Pick ${pk.pick_no}: ${pk.player.name}, ${pk.player.pos}. Open player details`, onPress: () => onOpen(pk.player) }))}
      />
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
        <SimMiniBoard rows={win.rows} from={win.from} to={win.to} />
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

export interface SimRecentChip {
  key: string;
  label: string;
  pos: string;
  aria?: string;
  onPress?: () => void;
}

/** The latest picks as a horizontally scrolling strip of position-underlined chips (shared by the redraft and rookie drafts). */
export function SimRecentStrip({ chips }: { chips: SimRecentChip[] }) {
  return (
    <ol className="flex gap-1.5 overflow-x-auto pb-0.5" aria-label="Recent picks" data-testid="recent-picks" style={{ scrollbarWidth: "none" }}>
      {chips.length === 0 ? (
        <li className="text-xs" style={{ color: "var(--color-text-muted)", minHeight: 32, display: "flex", alignItems: "center" }}>No picks yet. The first ones land here.</li>
      ) : (
        chips.map((chip) => {
          const colorVar = positionColorVar(chip.pos);
          const style = { minHeight: 32, borderRadius: "var(--radius-control)", background: "var(--color-surface-muted)", borderBottom: `3px solid ${colorVar ? `var(${colorVar})` : "var(--color-border-strong)"}` };
          return (
            <li key={chip.key} className="shrink-0">
              {chip.onPress ? (
                <button type="button" onClick={chip.onPress} className="whitespace-nowrap px-2 text-xs font-bold" style={style} aria-label={chip.aria ?? chip.label}>
                  {chip.label}
                </button>
              ) : (
                <span className="flex items-center whitespace-nowrap px-2 text-xs font-bold" style={style}>{chip.label}</span>
              )}
            </li>
          );
        })
      )}
    </ol>
  );
}

/** Rounds x picks of tiny position-coloured cells: yours outlined, the pick on the clock ringed, open slots dashed. */
export function SimMiniBoard({ rows, from, to }: { rows: SimMiniCell[][]; from: number; to: number }) {
  return (
    <div className="flex flex-col gap-1" data-testid="mini-board" role="img" aria-label={`Mini draft board, rounds ${from} to ${to}`}>
      {rows.map((row, i) => (
        <div key={from + i} className="flex items-center gap-1">
          <span className="shrink-0 text-[0.6875rem] font-extrabold tabular-nums" style={{ width: 22, color: "var(--color-text-muted)" }}>R{from + i}</span>
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
  );
}

/** The rookie draft's always-visible "who has been drafted": recent strip plus the mini board in a CompactModule. */
export function SimRookieOverview({ order, onClockPick, round, made, total }: { order: readonly { n: number; round: number; pick: string; is_yours: boolean; made: { id: string; name: string; pos: string } | null }[]; onClockPick: string | null | undefined; round: number; made: number; total: number }) {
  const rows = simRookieMiniBoard(order, onClockPick);
  const win = simDraftMiniWindow(rows, round);
  const chips = simRookieRecentChips(order);
  return (
    <div className="flex flex-col gap-2" data-testid="rookie-overview">
      <SimRecentStrip chips={chips} />
      <CompactModule id="rookie.board" title="Draft board" defaultOpen parts={[{ key: "n", text: `${made}/${total} picks`, strong: true }, chips[0] ? { key: "last", text: `last ${chips[0].label}` } : null]}>
        <SimMiniBoard rows={win.rows} from={win.from} to={win.to} />
      </CompactModule>
    </div>
  );
}
