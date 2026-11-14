import React, { useMemo, useState } from 'react';
import { View } from 'react-native';

import AppText from './AppText';

import { SimCollapse } from './SimGameDynastyParts';
import { SimRosterLine, createSimStyles, type SimCtx } from './SimGameParts';
import type { SimMoveHandle } from './SimMoveStrip';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simGameGate,
  simReserveReasonText,
  simReserveUsedLine,
  type SimGamePlayer,
  type SimSwapTarget,
  type SimLineupResponse,
  type SimMoveContext,
  type SimReserveMoveTo,
  type SimReserves,
} from '../lib/simGame';
import { simMoveNotes, simMoveSpecs, type SimMoveInput, type SimMoveKind } from '../lib/simMove';

/** Everything the move menu needs to know about the squads. */
export interface SimReserveState {
  reserves: SimReserves | null | undefined;
  rosterSize: number | null | undefined;
  rosterLimit: number | null | undefined;
}

function moveContext(state: SimReserveState): SimMoveContext {
  return { reserves: state.reserves, rosterSize: state.rosterSize, rosterLimit: state.rosterLimit };
}

/** What a screen tells the row about the lineup: which slots the player fits, or that he is a starter changing his own slot. */
export interface SimRowMoveOptions {
  swapTargets?: readonly SimSwapTarget[] | null;
  changeSlot?: string | null;
  lineupLocked?: boolean;
  onSwapTo?: (index: number) => void | Promise<unknown>;
  onChangeSlot?: () => void;
  /** Hide the trade block action (an incoming / non-tradable context). */
  noBlock?: boolean;
  /** Starters cannot be cut from the lineup (bench, IR and taxi can). */
  noCut?: boolean;
}

/**
 * The runtime behind every roster row's Move strip: IR / taxi / activate / taxi swap through the one move endpoint (a move the
 * backend refuses shows its message under that row's strip), the trade block toggle, cut and swap through the screen's own
 * handlers. `handleFor(player, options)` returns what SimPlayerLine's `move` prop takes: the possible specs and one `run`.
 */
export function useSimRosterMoves({
  ctx,
  state,
  taxi = [],
  onMoved,
  onCut,
}: {
  ctx: SimCtx;
  state: SimReserveState;
  taxi?: SimGamePlayer[];
  onMoved: (body: SimLineupResponse, player: SimGamePlayer, to: SimReserveMoveTo) => void;
  onCut?: (player: SimGamePlayer) => void | Promise<unknown>;
}) {
  const [refusal, setRefusal] = useState<{ id: string; message: string } | null>(null);
  const reservesOn = Boolean(state.reserves?.enabled);
  const blocksOn = (ctx.game.settings.block_v ?? 0) >= 1;

  async function reserveMove(player: SimGamePlayer, to: SimReserveMoveTo): Promise<boolean> {
    setRefusal(null);
    try {
      const body = await api.moveSimPlayer(ctx.gameId, { player_id: player.id, to });
      const gate = simGameGate(body);
      if (gate.kind === 'ready') {
        onMoved(body, player, to);
        return true;
      }
      if (gate.kind === 'blocked') setRefusal({ id: player.id, message: simReserveReasonText(gate.reason, body.message) });
      else await ctx.call(async () => body); // paywall, conflict and busy go through the one shared call path
    } catch (error) {
      const status = (error as { status?: number } | null)?.status;
      if (status === 409 || status === 503 || status === 404) await ctx.call(async () => Promise.reject(error));
      else setRefusal({ id: player.id, message: error instanceof Error && error.message ? error.message : 'Could not move him. Try again.' });
    }
    return false;
  }

  async function swapOnto(player: SimGamePlayer, other: SimGamePlayer) {
    // Promote the taxi player first (that frees the taxi slot), then move him in.
    setRefusal(null);
    try {
      const freed = await api.moveSimPlayer(ctx.gameId, { player_id: other.id, to: 'roster' });
      const gate = simGameGate(freed);
      if (gate.kind === 'blocked') {
        setRefusal({ id: player.id, message: simReserveReasonText(gate.reason, freed.message) });
        return;
      }
      if (gate.kind !== 'ready') {
        await ctx.call(async () => freed);
        return;
      }
    } catch {
      setRefusal({ id: player.id, message: 'Could not swap. Try again.' });
      return;
    }
    await reserveMove(player, 'taxi');
  }

  async function toggleBlock(player: SimGamePlayer) {
    const on = Boolean(player.block?.mine);
    const res = await ctx.call(() => api.putSimBlock(ctx.gameId, { asset_id: player.id, on: !on }));
    if (res && !res.reason) {
      ctx.bump();
      ctx.notify(!on ? `${player.name} is on your block.` : `${player.name} is off your block.`, 'success');
    }
  }

  return function handleFor(player: SimGamePlayer, o: SimRowMoveOptions = {}): SimMoveHandle {
    const input: SimMoveInput = {
      player,
      reserve: reservesOn ? moveContext(state) : null,
      taxi,
      swapTargets: o.swapTargets,
      changeSlot: o.changeSlot,
      lineupLocked: o.lineupLocked,
      canCut: Boolean(onCut) && !o.noCut,
      block: blocksOn && !o.noBlock && player.pos !== 'K' && player.pos !== 'DEF' ? { on: Boolean(player.block?.mine) } : null,
      profile: true,
    };
    const specs = simMoveSpecs(input);
    const run = async (kind: SimMoveKind, key?: string) => {
      if (kind === 'swap') return key != null ? o.onSwapTo?.(Number(key)) : o.onChangeSlot?.();
      if (kind === 'roster' || kind === 'ir' || kind === 'taxi') return reserveMove(player, kind);
      if (kind === 'taxi_swap') {
        const other = taxi.find((t) => t.id === key);
        return other ? swapOnto(player, other) : undefined;
      }
      if (kind === 'block') return toggleBlock(player);
      if (kind === 'cut') return onCut?.(player);
      return undefined;
    };
    return { specs, run, notes: simMoveNotes(input), refusal: refusal?.id === player.id ? refusal.message : null };
  };
}

/**
 * IR and Taxi groups for the Team tab, below the bench: a summary line with used / slots first, each group collapsible,
 * every row the same single-Move row (Activate / Promote, Swap onto taxi, Cut, Profile).
 */
export function SimReserveGroups({
  ir,
  taxi,
  state,
  openPlayer,
  handleFor,
}: {
  ir: SimGamePlayer[];
  taxi: SimGamePlayer[];
  state: SimReserveState;
  openPlayer: (player: SimGamePlayer) => void;
  handleFor: (player: SimGamePlayer, o?: SimRowMoveOptions) => SimMoveHandle;
}) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const r = state.reserves;
  if (!r) return null;
  const groups = [
    { kind: 'ir' as const, title: 'Injured reserve', players: ir, slots: r.ir_slots, empty: 'Nobody on IR. An injured player can go here and stops using a roster spot.' },
    { kind: 'taxi' as const, title: 'Taxi squad', players: taxi, slots: r.taxi_slots, empty: 'Nobody on the taxi squad. Rookies and young players can stash here and do not use a roster spot.' },
  ].filter((g) => g.slots > 0 || g.players.length > 0);
  if (groups.length === 0) return null;
  return (
    <View style={common.stack} testID="reserve-groups">
      <AppText style={common.muted} testID="reserve-summary">
        {groups.map((g) => simReserveUsedLine(g.kind, r)).join(' · ')}. These players do not score or count toward the roster limit.
      </AppText>
      {groups.map((g) => (
        <SimCollapse key={g.kind} title={g.title} summary={simReserveUsedLine(g.kind, r)} tone={g.kind === 'ir' ? 'danger' : 'accent'} defaultOpen={g.players.length > 0} testID={`reserve-${g.kind}`}>
          {g.players.length === 0 ? (
            <AppText style={common.muted}>{g.empty}</AppText>
          ) : (
            g.players.map((player) => {
              const p = { ...player, squad: g.kind };
              return <SimRosterLine key={player.id} player={p} suppressBadges={[g.kind]} onOpen={openPlayer} move={handleFor(p, { noBlock: true })} />;
            })
          )}
        </SimCollapse>
      ))}
    </View>
  );
}
