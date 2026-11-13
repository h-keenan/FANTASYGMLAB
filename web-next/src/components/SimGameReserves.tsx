"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { SimCollapse, SimPlayerChips } from "@/components/SimGameDynastyParts";
import { SimPlayerLine, SimSheet, SimStat, type SimCtx } from "@/components/SimGameParts";
import { api } from "@/lib/api";
import {
  simFmtPts,
  simGameGate,
  simReserveActions,
  simReserveReasonText,
  simReserveUsedLine,
  type SimGamePlayer,
  type SimLineupResponse,
  type SimMoveContext,
  type SimReserveAction,
  type SimReserveMoveTo,
  type SimReserves,
} from "@/lib/simGame";

/** Everything the move menu needs to know about the squads. */
export interface SimReserveState {
  reserves: SimReserves | null | undefined;
  rosterSize: number | null | undefined;
  rosterLimit: number | null | undefined;
}

function moveContext(state: SimReserveState): SimMoveContext {
  return { reserves: state.reserves, rosterSize: state.rosterSize, rosterLimit: state.rosterLimit };
}

/**
 * The per-player move menu as a sheet: Move to IR, Move to taxi, Activate or
 * Promote. A move the rules already forbid is disabled with its reason under
 * it; one the backend refuses shows the backend's message inline (the sheet
 * stays open so the player can try something else).
 */
export function SimReserveSheet({
  ctx,
  player,
  state,
  onClose,
  onMoved,
}: {
  ctx: SimCtx;
  player: SimGamePlayer;
  state: SimReserveState;
  onClose: () => void;
  onMoved: (body: SimLineupResponse, player: SimGamePlayer, to: SimReserveMoveTo) => void;
}) {
  const [busy, setBusy] = useState<SimReserveMoveTo | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const actions = simReserveActions(player, moveContext(state));

  async function go(action: SimReserveAction) {
    setBusy(action.to);
    setRefusal(null);
    try {
      const body = await api.moveSimPlayer(ctx.gameId, { player_id: player.id, to: action.to });
      const gate = simGameGate(body);
      if (gate.kind === "ready") {
        onMoved(body, player, action.to);
        return;
      }
      if (gate.kind === "blocked") {
        setRefusal(simReserveReasonText(gate.reason, body.message));
      } else {
        // Paywall, conflict and busy are handled by the one shared call path.
        await ctx.call(async () => body);
      }
    } catch (error) {
      const status = (error as { status?: number } | null)?.status;
      if (status === 409 || status === 503 || status === 404) await ctx.call(async () => Promise.reject(error));
      else setRefusal(error instanceof Error && error.message ? error.message : "Could not move him. Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <SimSheet title={`Move ${player.name}`} onClose={onClose}>
      <p className="pr-10 text-lg font-extrabold">
        {player.name}
      </p>
      <div className="flex items-center gap-2 pt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
        <span>{player.pos}{player.team ? ` · ${player.team}` : ""}</span>
        <SimPlayerChips player={player} />
      </div>
      <ul className="flex flex-col gap-2 pt-3" aria-label="Moves">
        {actions.map((action) => (
          <li key={action.to} className="flex flex-col gap-1">
            <Button
              fullWidth
              variant={action.check.ok ? "primary" : "secondary"}
              disabled={!action.check.ok || busy !== null}
              loading={busy === action.to}
              onClick={() => void go(action)}
            >
              {action.label}
            </Button>
            {!action.check.ok && action.check.reason ? (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid={`reserve-hint-${action.to}`}>
                {simReserveReasonText(action.check.reason)}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {refusal ? (
        <p className="pt-2 text-sm font-semibold" role="alert" style={{ color: "var(--color-warning)" }} data-testid="reserve-refusal">
          {refusal}
        </p>
      ) : null}
      <Button variant="ghost" className="mt-2" onClick={onClose}>
        Close
      </Button>
    </SimSheet>
  );
}

/** The "Move" button for a roster row; opens the sheet through `onOpen`. */
export function SimReserveButton({ player, onOpen }: { player: SimGamePlayer; onOpen: (player: SimGamePlayer) => void }) {
  return (
    <Button size="sm" variant="ghost" aria-label={`Move ${player.name} to IR, taxi or roster`} onClick={() => onOpen(player)}>
      Move
    </Button>
  );
}

/**
 * IR and Taxi groups for the Team tab, below the bench: a summary line with
 * used / slots first, each group collapsible, every row with chips and Move.
 */
export function SimReserveGroups({
  ir,
  taxi,
  state,
  onOpen,
  openPlayer,
  cutting = null,
  onAskCut,
  onCut,
}: {
  ir: SimGamePlayer[];
  taxi: SimGamePlayer[];
  state: SimReserveState;
  onOpen: (player: SimGamePlayer) => void;
  openPlayer: (player: SimGamePlayer) => void;
  /** Id awaiting a cut confirmation, and the handlers: IR and taxi players can be released like anyone else (Sleeper rules). */
  cutting?: string | null;
  onAskCut?: (id: string | null) => void;
  onCut?: (player: SimGamePlayer) => void;
}) {
  const r = state.reserves;
  if (!r) return null;
  const groups = [
    { kind: "ir" as const, title: "Injured reserve", players: ir, slots: r.ir_slots, empty: "Nobody on IR. An injured player can go here and stops using a roster spot." },
    { kind: "taxi" as const, title: "Taxi squad", players: taxi, slots: r.taxi_slots, empty: "Nobody on the taxi squad. Rookies and young players can stash here and do not use a roster spot." },
  ].filter((g) => g.slots > 0 || g.players.length > 0);
  if (groups.length === 0) return null;
  return (
    <div className="flex flex-col gap-2" data-testid="reserve-groups">
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="reserve-summary">
        {groups.map((g) => simReserveUsedLine(g.kind, r)).join(" · ")}. These players do not score or count toward the roster limit.
      </p>
      {groups.map((g) => (
        <SimCollapse key={g.kind} title={g.title} summary={simReserveUsedLine(g.kind, r)} tone={g.kind === "ir" ? "danger" : "accent"} defaultOpen={g.players.length > 0} testId={`reserve-${g.kind}`}>
          {g.players.length === 0 ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{g.empty}</p>
          ) : (
            g.players.map((player) => (
              <SimPlayerLine
                key={player.id}
                player={player}
                muted
                onOpen={openPlayer}
                extra={<SimPlayerChips player={{ ...player, squad: g.kind }} />}
                trailing={
                  cutting === player.id && onCut ? (
                    <>
                      <Button size="sm" variant="danger" onClick={() => onCut(player)}>Cut {player.name.split(" ").slice(-1)[0]}</Button>
                      <Button size="sm" variant="ghost" onClick={() => onAskCut?.(null)}>Keep</Button>
                    </>
                  ) : (
                    <>
                      <SimStat label="Proj" value={simFmtPts(player.projection)} />
                      <SimReserveButton player={{ ...player, squad: g.kind }} onOpen={onOpen} />
                      {onCut && onAskCut ? (
                        <Button size="sm" variant="ghost" aria-label={`Cut ${player.name}`} onClick={() => onAskCut(player.id)}>Cut</Button>
                      ) : null}
                    </>
                  )
                }
              />
            ))
          )}
        </SimCollapse>
      ))}
    </div>
  );
}
