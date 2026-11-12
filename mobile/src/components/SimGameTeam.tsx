import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPlayerBrowser } from './SimGamePlayers';
import { SimPlayerChip, SimPlayerLine, SimSheet, SimStat, SimToneBadge, createSimStyles, type SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simAssignSlot,
  simClaimPayload,
  simFmtPts,
  simSlotRepeatsPosition,
  simLineupPayload,
  simMatchupLine,
  simNeedsDrop,
  simPositionsFor,
  simSlotAccepts,
  simSlotCandidates,
  simSlotLabels,
  simWarningText,
  type SimGamePlayer,
  type SimLineupResponse,
  type SimSlot,
  type SimWaiverClaim,
} from '../lib/simGame';
import { spacing, type ThemeColors } from '../theme';

/** Lineup, bench and this week's matchup. Every change saves at once (PUT /lineup). */
export function SimTeamTab({ ctx, onTrade }: { ctx: SimCtx; onTrade: () => void }) {
  const { gameId, game, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [lineup, setLineup] = useState<SimLineupResponse | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [pickSlot, setPickSlot] = useState<number | null>(null);
  const [cutting, setCutting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimLineup(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) {
          setState('error');
          return;
        }
        setLineup(body);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, attempt]);

  const refreshGame = useCallback(async () => {
    await ctx.reloadGame();
  }, [ctx]);

  async function save(slots: NonNullable<SimLineupResponse['slots']>, bench: SimGamePlayer[]) {
    const previous = lineup;
    setLineup((l) => (l ? { ...l, slots, bench } : l));
    setSaving(true);
    const body = await call(() => api.putSimLineup(gameId, simLineupPayload(slots)));
    setSaving(false);
    if (body) {
      setLineup(body);
      await refreshGame();
    } else {
      setLineup(previous);
    }
  }

  async function auto() {
    setSaving(true);
    const body = await call(() => api.autoSimLineup(gameId));
    setSaving(false);
    if (body) {
      setLineup(body);
      await refreshGame();
    }
  }

  async function cut(player: SimGamePlayer) {
    setCutting(null);
    const body = await call(() => api.cutSimPlayer(gameId, player.id));
    if (body) {
      ctx.notify(`Cut ${player.name}. He is back in the free-agent pool.`, 'success');
      ctx.bump();
      await refreshGame();
    }
  }

  if (state === 'loading') {
    return (
      <View style={common.stack}>
        <SkeletonCard rows={2} />
        <SkeletonCard rows={6} />
      </View>
    );
  }
  if (state === 'error' || !lineup?.slots) {
    return (
      <ErrorState
        title="Your lineup did not load"
        message="Check your connection and try again."
        onRetry={() => {
          setState('loading');
          setAttempt((n) => n + 1);
        }}
      />
    );
  }

  const slots = lineup.slots;
  const bench = lineup.bench ?? [];
  const labels = simSlotLabels(slots);
  const week = game.this_week;
  const overLimit = (game.pending?.cuts_needed ?? 0) > 0;
  const warnings = lineup.warnings ?? [];
  const playerById = Object.fromEntries([...slots.map((s) => s.player), ...bench].filter(Boolean).map((p) => [p!.id, p!]));
  const candidates = pickSlot != null ? simSlotCandidates(slots[pickSlot].slot, slots, bench) : [];

  return (
    <View style={common.stack}>
      {week ? (
        <AccentCard accent={week.bye ? colors.warning : colors.danger}>
          <AppText style={styles.kicker}>Week {week.week} matchup</AppText>
          <View style={common.rowBetween}>
            <View style={common.grow}>
              <AppText style={common.bodyStrong}>You</AppText>
              <AppText style={styles.projection} testID="your-projection">
                {simFmtPts(week.your_projection)}
              </AppText>
            </View>
            <AppText style={common.muted}>vs</AppText>
            <View style={[common.grow, styles.right]}>
              <AppText style={[common.bodyStrong, common.center]}>{week.opponent?.name ?? 'Bye week'}</AppText>
              <AppText style={styles.projection}>{week.opponent ? simFmtPts(week.opponent_projection) : '-'}</AppText>
            </View>
          </View>
          <AppText style={common.small}>{simMatchupLine(week)}</AppText>
        </AccentCard>
      ) : null}

      {overLimit ? (
        <AccentCard accent={colors.danger} compact>
          <AppText style={common.bodyStrong} accessibilityRole="alert">
            Roster over the limit: cut {game.pending?.cuts_needed} player{game.pending?.cuts_needed === 1 ? '' : 's'} from your bench before you advance.
          </AppText>
        </AccentCard>
      ) : null}

      {warnings.length > 0 ? (
        <AccentCard accent={colors.warning} compact>
          {warnings.map((w, i) => (
            <View key={i} style={common.stack}>
              {w.player_id && playerById[w.player_id] ? <SimPlayerChip player={playerById[w.player_id]} /> : null}
              <AppText style={common.small}>{simWarningText(w, w.player_id ? playerById[w.player_id]?.name : undefined)}</AppText>
            </View>
          ))}
        </AccentCard>
      ) : null}

      <View>
        <SectionHeading
          title="Lineup"
          caption={`Projected ${simFmtPts(lineup.projected_total)} points`}
          right={<Button size="sm" variant="secondary" label="Auto-set" loading={saving} onPress={auto} />}
        />
        {slots.map((slot, index) => (
          <View key={`${slot.slot}-${index}`} style={[common.row, common.divider]}>
            <View style={common.slotCol}>
              <PositionBadge position={slot.slot} label={labels[index]} />
            </View>
            {slot.player ? (
              <View style={common.grow}>
                <SimPlayerLine
                  player={slot.player}
                  hidePosition={simSlotRepeatsPosition(slot.slot, slot.player.pos)}
                  onOpen={ctx.openPlayer}
                  trailing={
                    <>
                      <SimStat label="Proj" value={simFmtPts(slot.player.projection)} />
                      <Button size="sm" variant="secondary" label="Change" onPress={() => setPickSlot(index)} />
                    </>
                  }
                />
              </View>
            ) : (
              <View style={[common.rowBetween, common.grow, styles.emptySlot]}>
                <AppText style={[common.small, { color: colors.warning }]}>Empty slot</AppText>
                <Button size="sm" label="Fill" onPress={() => setPickSlot(index)} />
              </View>
            )}
          </View>
        ))}
      </View>

      <View>
        <SectionHeading title="Bench" caption={`${lineup.roster_size ?? 0} of ${lineup.roster_limit ?? 16} roster spots`} />
        {bench.length === 0 ? (
          <EmptyState icon="albums-outline" title="Empty bench" subtitle="Add free agents from the Players tab." />
        ) : (
          bench.map((player) => (
            <SimPlayerLine
              key={player.id}
              player={player}
              muted
              onOpen={ctx.openPlayer}
              trailing={
                cutting === player.id ? (
                  <>
                    <Button size="sm" variant="danger" label={`Cut ${player.name.split(' ').slice(-1)[0]}`} onPress={() => cut(player)} />
                    <Button size="sm" variant="ghost" label="Keep" onPress={() => setCutting(null)} />
                  </>
                ) : (
                  <>
                    <SimStat label="Proj" value={simFmtPts(player.projection)} />
                    <Button size="sm" variant={overLimit ? 'dangerOutline' : 'ghost'} label="Cut" onPress={() => setCutting(player.id)} />
                  </>
                )
              }
            />
          ))
        )}
        {game.can_trade ? <Button size="sm" variant="ghost" label="Shop a trade" onPress={onTrade} style={styles.shop} /> : null}
      </View>

      {pickSlot != null ? (
        <SimSheet title={`Choose your ${labels[pickSlot]}`} onClose={() => setPickSlot(null)}>
          {candidates.length === 0 ? (
            <AppText style={common.small}>No one on your roster fits this slot.</AppText>
          ) : (
            candidates.map(({ player, from }) => (
              <SimPlayerLine
                key={player.id}
                player={player}
                selected={slots[pickSlot].player?.id === player.id}
                extra={from === 'slot' ? <SimToneBadge label="Starting elsewhere: swaps" tone="muted" /> : undefined}
                trailing={
                  <>
                    <SimStat label="Proj" value={simFmtPts(player.projection)} />
                    <Button
                      size="sm"
                      label="Start"
                      disabled={slots[pickSlot].player?.id === player.id}
                      onPress={() => {
                        const next = simAssignSlot({ slots, bench }, pickSlot, player);
                        setPickSlot(null);
                        void save(next.slots, next.bench);
                      }}
                    />
                  </>
                }
              />
            ))
          )}
          {slots[pickSlot].player ? (
            <Button
              variant="secondary"
              label="Move to bench"
              onPress={() => {
                const next = simAssignSlot({ slots, bench }, pickSlot, null);
                setPickSlot(null);
                void save(next.slots, next.bench);
              }}
            />
          ) : null}
        </SimSheet>
      ) : null}
    </View>
  );
}

/** Add (with an optional drop and start slot) as a waiver claim. */
function ClaimSheet({
  ctx,
  player,
  roster,
  onClose,
  onClaimed,
}: {
  ctx: SimCtx;
  player: SimGamePlayer;
  roster: SimGamePlayer[];
  onClose: () => void;
  onClaimed: (claims: SimWaiverClaim[]) => void;
}) {
  const { game } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [dropId, setDropId] = useState('');
  const [slot, setSlot] = useState<SimSlot | ''>('');
  const [busy, setBusy] = useState(false);
  const mustDrop = simNeedsDrop(roster.length, game.settings.roster_limit);
  const eligibleSlots = Array.from(new Set(game.settings.slots)).filter((s) => simSlotAccepts(s, player.pos));
  const payload = simClaimPayload({ add: player, drop: roster.find((p) => p.id === dropId) ?? null, startSlot: (slot || null) as SimSlot | null });

  async function submit() {
    if (!payload) return;
    setBusy(true);
    const body = await ctx.call(() => api.claimSimWaiver(ctx.gameId, payload));
    setBusy(false);
    if (body) {
      ctx.notify(`Claim queued for ${player.name}. It resolves when you advance the week.`, 'success');
      onClaimed(body.claims ?? []);
      await ctx.reloadGame();
      onClose();
    }
  }

  return (
    <SimSheet title={`Claim ${player.name}`} onClose={onClose}>
      <SimPlayerChip player={player} size={40} />
      <AppText style={common.muted}>Claims resolve when you advance, worst record first. Another team may get him first.</AppText>
      <View style={common.stack}>
        <AppText style={common.bodyStrong}>{mustDrop ? 'Drop (your roster is full)' : 'Drop (optional)'}</AppText>
        {!mustDrop ? (
          <Button size="sm" variant={dropId === '' ? 'primary' : 'secondary'} label="No drop" onPress={() => setDropId('')} style={{ alignSelf: 'flex-start' }} />
        ) : null}
        {roster.map((p) => (
          <SimPlayerLine
            key={p.id}
            player={p}
            selected={dropId === p.id}
            trailing={
              <>
                <SimStat label="Proj" value={simFmtPts(p.projection)} />
                <Button size="sm" variant={dropId === p.id ? 'primary' : 'secondary'} label={dropId === p.id ? 'Dropping' : 'Drop'} onPress={() => setDropId(dropId === p.id ? '' : p.id)} />
              </>
            }
          />
        ))}
        {eligibleSlots.length > 0 ? (
          <View style={common.tight}>
            <AppText style={common.bodyStrong}>Start him if the claim wins (optional)</AppText>
            <SegmentedTabBar<string>
              scrollable
              options={[{ key: '', label: 'Bench' }, ...eligibleSlots.map((s) => ({ key: s as string, label: s }))]}
              active={slot}
              onChange={(key) => setSlot(key as SimSlot | '')}
            />
          </View>
        ) : null}
        <Button label="Queue claim" loading={busy} disabled={mustDrop && !dropId} onPress={submit} />
      </View>
    </SimSheet>
  );
}

/** Search every player, or work the waiver wire. */
export function SimPlayersTab({
  ctx,
  claims,
  setClaims,
  onTradeFor,
}: {
  ctx: SimCtx;
  claims: SimWaiverClaim[];
  setClaims: (claims: SimWaiverClaim[]) => void;
  onTradeFor: (player: SimGamePlayer) => void;
}) {
  const { gameId, game, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [mode, setMode] = useState<'all' | 'waivers'>('all');
  const [roster, setRoster] = useState<SimGamePlayer[]>([]);
  const [claiming, setClaiming] = useState<SimGamePlayer | null>(null);
  const teamId = game.you?.team_id;

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api
      .getSimGameTeam(gameId, teamId)
      .then((body) => {
        if (!cancelled) setRoster(body.players ?? []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, ctx.tick]);

  async function cancel(claim: SimWaiverClaim) {
    const body = await call(() => api.cancelSimWaiver(gameId, claim.id));
    if (body) {
      setClaims(body.claims ?? []);
      await ctx.reloadGame();
    }
  }

  const queuedIds = new Set(claims.map((c) => c.add.id));
  const actions = (player: SimGamePlayer) => {
    if (player.owner?.type === 'free_agent') {
      return queuedIds.has(player.id) ? <SimToneBadge label="Claim queued" tone="accent" /> : <Button size="sm" label="Add" onPress={() => setClaiming(player)} />;
    }
    if (player.owner?.type === 'ai' && game.can_trade) {
      return <Button size="sm" variant="secondary" label="Trade" onPress={() => onTradeFor(player)} />;
    }
    return null;
  };

  return (
    <View style={common.stack}>
      <SegmentedTabBar<'all' | 'waivers'>
        options={[
          { key: 'all', label: 'All players' },
          { key: 'waivers', label: `Waivers${claims.length ? ` ${claims.length}` : ''}` },
        ]}
        active={mode}
        onChange={setMode}
      />
      {mode === 'waivers' && claims.length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Queued claims" caption="Resolve at Advance, worst record first." />
          {claims.map((claim) => (
            <AccentCard key={claim.id} accent={colors.accent} compact>
              <View style={common.rowBetween}>
                <View style={[common.stack, common.grow]}>
                  <SimPlayerChip player={claim.add} />
                  {claim.drop ? <AppText style={common.muted}>Drops {claim.drop.name} ({claim.drop.pos})</AppText> : null}
                  {claim.start_slot ? <AppText style={common.muted}>Starts at {claim.start_slot}</AppText> : null}
                </View>
                <Button size="sm" variant="ghost" label="Cancel" onPress={() => cancel(claim)} />
              </View>
            </AccentCard>
          ))}
        </View>
      ) : null}
      {mode === 'waivers' && claims.length === 0 && (game.pending?.claims ?? 0) > 0 ? (
        <AppText style={common.muted}>
          {game.pending?.claims} claim{game.pending?.claims === 1 ? ' is' : 's are'} already queued for this week.
        </AppText>
      ) : null}
      <SimPlayerBrowser key={mode} gameId={gameId} fixedStatus={mode === 'waivers' ? 'available' : undefined} positions={simPositionsFor(game.settings.slots)} onOpen={ctx.openPlayer} actions={actions} refreshKey={ctx.tick} />
      {claiming ? <ClaimSheet ctx={ctx} player={claiming} roster={roster} onClose={() => setClaiming(null)} onClaimed={setClaims} /> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    projection: { fontSize: 24, fontWeight: '800', color: colors.textPrimary },
    right: { alignItems: 'flex-end' },
    emptySlot: { paddingVertical: spacing.sm },
    shop: { alignSelf: 'flex-start' },
  });
}
