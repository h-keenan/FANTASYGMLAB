import React, { useMemo, useState } from 'react';
import { View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import { SimCollapse, SimPlayerChips } from './SimGameDynastyParts';
import { SimPlayerLine, SimSheet, SimStat, createSimStyles, type SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
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
} from '../lib/simGame';

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
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [busy, setBusy] = useState<SimReserveMoveTo | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);
  const actions = simReserveActions(player, moveContext(state));

  async function go(action: SimReserveAction) {
    setBusy(action.to);
    setRefusal(null);
    try {
      const body = await api.moveSimPlayer(ctx.gameId, { player_id: player.id, to: action.to });
      const gate = simGameGate(body);
      if (gate.kind === 'ready') {
        onMoved(body, player, action.to);
        return;
      }
      if (gate.kind === 'blocked') {
        setRefusal(simReserveReasonText(gate.reason, body.message));
      } else {
        // Paywall, conflict and busy are handled by the one shared call path.
        await ctx.call(async () => body);
      }
    } catch (error) {
      const status = (error as { status?: number } | null)?.status;
      if (status === 409 || status === 503 || status === 404) await ctx.call(async () => Promise.reject(error));
      else setRefusal(error instanceof Error && error.message ? error.message : 'Could not move him. Try again.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <SimSheet title={`Move ${player.name}`} onClose={onClose}>
      <View style={common.wrapRow}>
        <AppText style={common.small}>
          {player.pos}
          {player.team ? ` · ${player.team}` : ''}
        </AppText>
        <SimPlayerChips player={player} />
      </View>
      <View style={common.stack}>
        {actions.map((action) => (
          <View key={action.to} style={common.tight}>
            <Button
              variant={action.check.ok ? 'primary' : 'secondary'}
              disabled={!action.check.ok || busy !== null}
              loading={busy === action.to}
              label={action.label}
              onPress={() => void go(action)}
            />
            {!action.check.ok && action.check.reason ? (
              <AppText style={common.muted} testID={`reserve-hint-${action.to}`}>
                {simReserveReasonText(action.check.reason)}
              </AppText>
            ) : null}
          </View>
        ))}
      </View>
      {refusal ? (
        <AppText style={[common.bodyStrong, { color: colors.warning }]} accessibilityRole="alert" testID="reserve-refusal">
          {refusal}
        </AppText>
      ) : null}
      <Button variant="ghost" label="Close" onPress={onClose} />
    </SimSheet>
  );
}

/** The "Move" button for a roster row; opens the sheet through `onOpen`. */
export function SimReserveButton({ player, onOpen }: { player: SimGamePlayer; onOpen: (player: SimGamePlayer) => void }) {
  return <Button size="sm" variant="ghost" label="Move" onPress={() => onOpen(player)} />;
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
}: {
  ir: SimGamePlayer[];
  taxi: SimGamePlayer[];
  state: SimReserveState;
  onOpen: (player: SimGamePlayer) => void;
  openPlayer: (player: SimGamePlayer) => void;
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
            g.players.map((player) => (
              <SimPlayerLine
                key={player.id}
                player={player}
                muted
                onOpen={openPlayer}
                extra={<SimPlayerChips player={{ ...player, squad: g.kind }} />}
                trailing={
                  <>
                    <SimStat label="Proj" value={simFmtPts(player.projection)} />
                    <SimReserveButton player={{ ...player, squad: g.kind }} onOpen={onOpen} />
                  </>
                }
              />
            ))
          )}
        </SimCollapse>
      ))}
    </View>
  );
}
