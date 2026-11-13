import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import SimGlyph from './SimGlyph';
import { ReviewGlyphChip } from './SeasonReviewSections';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPickLine, SimPlayerChips, useSimPicks } from './SimGameDynastyParts';
import { SimPlayerBrowser } from './SimGamePlayers';
import { SimReserveButton, SimReserveGroups, SimReserveSheet } from './SimGameReserves';
import { SimFold, SimIconButton, SimPlayerChip, SimPlayerLine, SimSectionTitle, SimSheet, SimStat, SimTeamLink, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simAssignSlot,
  simClaimPayload,
  simFmtPts,
  simHeadshotId,
  simPlayerInitials,
  simSlotRepeatsPosition,
  simLineupPayload,
  simMatchupLine,
  simMatchupTone,
  simNeedsDrop,
  simPicksOf,
  simPicksSummaryLine,
  simPickGroups,
  simFilterPositionsFor,
  simReservesOn,
  simSlotAccepts,
  simSlotCandidates,
  simSlotLabels,
  simWarningText,
  type SimGamePlayer,
  type SimLineupResponse,
  type SimPickAsset,
  type SimSlot,
  type SimWaiverClaim,
} from '../lib/simGame';
import { positionColor, radii, spacing, type ThemeColors } from '../theme';

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
  const [moving, setMoving] = useState<SimGamePlayer | null>(null);
  const picks = useSimPicks(ctx);

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
  const reservesOn = simReservesOn(game.settings, lineup.reserves);
  const reserveState = { reserves: lineup.reserves, rosterSize: lineup.roster_size, rosterLimit: lineup.roster_limit };
  const myPicks = simPicksOf(picks, game.you?.team_id);

  return (
    <View style={common.stack}>
      {week ? (
        <AccentCard accent={simToneColor(simMatchupTone(week), colors)} compact>
          <View style={common.rowBetween}>
            <View style={[common.row, common.grow]}>
              <ReviewGlyphChip glyph="game" tone={simMatchupTone(week)} size={24} />
              <AppText style={styles.kicker}>Week {week.week}</AppText>
              {week.opponent ? <SimTeamLink teamId={week.opponent.team_id} name={week.opponent.name} size={24} /> : <AppText style={common.bodyStrong}>Bye week</AppText>}
            </View>
            <View style={common.row}>
              <AppText style={[styles.projection, week.opponent && week.your_projection >= week.opponent_projection && { color: colors.success }]} testID="your-projection">
                {simFmtPts(week.your_projection)}
              </AppText>
              {week.opponent ? <AppText style={common.muted}>vs</AppText> : null}
              {week.opponent ? <AppText style={[styles.projection, week.opponent_projection > week.your_projection && { color: colors.danger }]}>{simFmtPts(week.opponent_projection)}</AppText> : null}
            </View>
          </View>
          <AppText style={[common.small, { color: simToneColor(simMatchupTone(week), colors), fontWeight: '600' }]}>{simMatchupLine(week)} The full head-to-head is on Home.</AppText>
        </AccentCard>
      ) : null}

      {overLimit ? (
        <AccentCard accent={colors.danger} compact>
          <View style={common.row}>
            <ReviewGlyphChip glyph="injury" tone="danger" size={24} />
            <AppText style={[common.bodyStrong, common.grow]} accessibilityRole="alert">
              Roster over the limit: cut {game.pending?.cuts_needed} player{game.pending?.cuts_needed === 1 ? '' : 's'} from your bench before you advance.
            </AppText>
          </View>
        </AccentCard>
      ) : null}

      {warnings.length > 0 ? (
        <AccentCard accent={colors.warning} compact>
          {warnings.map((w, i) => (
            <View key={i} style={common.stack}>
              {w.player_id && playerById[w.player_id] ? <SimPlayerChip player={playerById[w.player_id]} /> : null}
              <View style={common.row}>
                <ReviewGlyphChip glyph="lineup" tone="warning" size={20} />
                <AppText style={[common.small, common.grow, { color: colors.warning }]}>{simWarningText(w, w.player_id ? playerById[w.player_id]?.name : undefined)}</AppText>
              </View>
            </View>
          ))}
        </AccentCard>
      ) : null}

      <View>
        <SimSectionTitle
          glyph="team"
          title="Lineup"
          caption={`Projected ${simFmtPts(lineup.projected_total)} points`}
          right={
            <Pressable
              onPress={auto}
              disabled={saving || lineup.locked}
              accessibilityRole="button"
              accessibilityLabel="Auto-set best lineup"
              accessibilityState={{ disabled: saving || lineup.locked, busy: saving }}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 36, paddingHorizontal: spacing.md, borderRadius: radii.pill, borderWidth: 1, borderColor: colors.borderStrong ?? colors.border, opacity: saving || lineup.locked ? 0.6 : 1 }}
            >
              <SimGlyph name="spark" color={colors.accent} size={14} />
              <AppText style={{ fontSize: 12.5, fontWeight: '800', color: colors.textPrimary }}>{saving ? 'Setting...' : 'Auto-set'}</AppText>
            </Pressable>
          }
        />
        {slots.map((slot, index) => (
          <LineupRow key={`${slot.slot}-${index}`} slotLabel={labels[index]} slot={slot.slot} player={slot.player} locked={lineup.locked} onOpen={ctx.openPlayer} onPick={() => setPickSlot(index)} onMove={reservesOn && slot.player?.status === 'out' ? setMoving : undefined} />
        ))}
      </View>

      <View>
        <SimSectionTitle glyph="bye" tone="muted" title="Bench" caption={`${lineup.roster_size ?? 0} of ${lineup.roster_limit ?? 16} roster spots`} />
        {bench.length === 0 ? (
          <EmptyState icon="albums-outline" title="Empty bench" subtitle="Add free agents from the Players tab." />
        ) : (
          bench.map((player) => (
            <SimPlayerLine
              key={player.id}
              player={player}
              muted
              onOpen={ctx.openPlayer}
              extra={<SimPlayerChips player={player} />}
              trailing={
                cutting === player.id ? (
                  <>
                    <Button size="sm" variant="danger" label={`Cut ${player.name.split(' ').slice(-1)[0]}`} onPress={() => cut(player)} />
                    <Button size="sm" variant="ghost" label="Keep" onPress={() => setCutting(null)} />
                  </>
                ) : (
                  <>
                    <SimStat label="Proj" value={simFmtPts(player.projection)} />
                    {reservesOn ? <SimReserveButton player={player} onOpen={setMoving} /> : null}
                    <Button size="sm" variant={overLimit ? 'dangerOutline' : 'ghost'} label="Cut" onPress={() => setCutting(player.id)} />
                  </>
                )
              }
            />
          ))
        )}
        {game.can_trade ? <Button size="sm" variant="ghost" label="Shop a trade" onPress={onTrade} style={styles.shop} /> : null}
        {reservesOn ? <SimReserveGroups ir={lineup.ir ?? []} taxi={lineup.taxi ?? []} state={reserveState} onOpen={setMoving} openPlayer={ctx.openPlayer} /> : null}
        {game.settings.mode === 'dynasty' && picks ? <SimYourPicks picks={myPicks} draftYear={picks.draft_year} /> : null}
      </View>

      {moving ? (
        <SimReserveSheet
          ctx={ctx}
          player={moving}
          state={reserveState}
          onClose={() => setMoving(null)}
          onMoved={(body, player, to) => {
            setMoving(null);
            setLineup(body);
            ctx.notify(`${player.name} ${to === 'ir' ? 'is on IR' : to === 'taxi' ? 'is on the taxi squad' : 'is back on your roster'}.`, 'success');
            ctx.bump();
            void refreshGame();
          }}
        />
      ) : null}

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

/** "Your picks": the shared fold (closed on phones), one summary line, then your picks by year and round. */
export function SimYourPicks({ picks, draftYear }: { picks: SimPickAsset[]; draftYear?: number | null }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const groups = simPickGroups(picks);
  return (
    <SimFold id="team.picks" glyph="league" title="Your picks" summary={<AppText style={common.muted}>{simPicksSummaryLine(picks)}</AppText>} testID="your-picks">
      {groups.length === 0 ? (
        <AppText style={common.muted}>You hold no draft picks. Trade for some on the Trades tab.</AppText>
      ) : (
        groups.map((group) => (
          <View key={group.season}>
            <AppText style={[common.small, { fontWeight: '700', paddingTop: spacing.xs }]}>{group.season}</AppText>
            {group.rounds
              .flatMap((r) => r.picks)
              .map((pick) => (
                <SimPickLine key={pick.id} pick={pick} draftYear={draftYear} />
              ))}
          </View>
        ))
      )}
    </SimFold>
  );
}

/** Add (with an optional drop and start slot) as a waiver claim. */
export function ClaimSheet({
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
      <AppText style={common.muted}>Claims resolve when you advance, before games are scored, worst record first. A claimed player can start that same week. Another team may get him first.</AppText>
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
          { key: 'all', label: 'All players', glyph: 'team' },
          { key: 'waivers', label: `Waivers${claims.length ? ` ${claims.length}` : ''}`, glyph: 'addDrop' },
        ]}
        active={mode}
        onChange={setMode}
      />
      {mode === 'waivers' && claims.length > 0 ? (
        <View style={common.stack}>
          <SimSectionTitle glyph="waiver" title="Queued claims" caption="Resolve at Advance, worst record first." />
          {claims.map((claim) => (
            <AccentCard key={claim.id} accent={colors.success} compact>
              <View style={common.rowBetween}>
                <View style={[common.stack, common.grow]}>
                  <View style={common.row}>
                    <ReviewGlyphChip glyph="waiver" tone="success" size={24} />
                    <SimPlayerChip player={claim.add} />
                  </View>
                  {claim.drop ? <AppText style={[common.muted, { color: colors.danger }]}>Drops {claim.drop.name} ({claim.drop.pos})</AppText> : null}
                  {claim.start_slot ? <AppText style={[common.muted, { color: colors.success }]}>Starts at {claim.start_slot}</AppText> : null}
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
      <SimPlayerBrowser key={mode} gameId={gameId} fixedStatus={mode === 'waivers' ? 'available' : undefined} positions={simFilterPositionsFor(game.settings.slots)} week={game.week} onOpen={ctx.openPlayer} actions={actions} refreshKey={ctx.tick} />
      {claiming ? <ClaimSheet ctx={ctx} player={claiming} roster={roster} onClose={() => setClaiming(null)} onClaimed={setClaims} /> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    projection: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
    right: { alignItems: 'flex-end' },
    emptySlot: { paddingVertical: spacing.sm },
    shop: { alignSelf: 'flex-start' },
  });
}

/**
 * One lineup row, one fixed layout for every row: slot badge (fixed width),
 * 32pt avatar, one-line name + subline, projection (fixed) and a 40pt
 * Change / Fill control. The player's own position shows only where the slot
 * does not already say it (FLEX, SUPERFLEX), as a small dot + label in the subline.
 */
function LineupRow({ slotLabel, slot, player, locked, onOpen, onPick, onMove }: { slotLabel: string; slot: SimSlot; player: SimGamePlayer | null; locked?: boolean; onOpen: (p: SimGamePlayer) => void; onPick: () => void; onMove?: (p: SimGamePlayer) => void }) {
  const { colors, isDark } = useThemeMode();
  const showPos = player ? !simSlotRepeatsPosition(slot, player.pos) : false;
  const posColor = player ? positionColor(player.pos, isDark, colors.textSecondary) : colors.textSecondary;
  const sub = player ? [player.team, player.status === 'out' ? 'Out' : player.status === 'bye' ? 'Bye' : null].filter(Boolean).join(' · ') : '';
  return (
    <View
      testID="lineup-row"
      style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 52, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }}
    >
      <View style={{ width: 52, alignItems: 'center' }}>
        <PositionBadge position={slot} label={slotLabel} />
      </View>
      {player ? (
        <Pressable
          onPress={() => onOpen(player)}
          accessibilityRole="button"
          accessibilityLabel={`${player.name}, ${player.pos}. Open player details`}
          style={{ flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 }}
        >
          <PlayerAvatar playerId={simHeadshotId(player)} fallbackLabel={simPlayerInitials(player)} size={32} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <AppText style={{ fontSize: 14, fontWeight: '800', color: player.status === 'healthy' ? colors.textPrimary : colors.textTertiary }} numberOfLines={1}>
              {player.name}
            </AppText>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              {showPos ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }} accessibilityLabel={player.pos}>
                  <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: posColor }} />
                  <AppText style={{ fontSize: 12, fontWeight: '800', color: posColor }}>{player.pos}</AppText>
                </View>
              ) : null}
              <AppText style={{ flex: 1, fontSize: 12, color: colors.textTertiary }} numberOfLines={1}>
                {sub}
              </AppText>
            </View>
          </View>
        </Pressable>
      ) : (
        <AppText style={{ flex: 1, fontSize: 13, color: colors.warning }}>Empty slot</AppText>
      )}
      <AppText style={{ width: 44, textAlign: 'right', fontSize: 14, fontWeight: '800', color: colors.textPrimary }}>{player ? simFmtPts(player.projection) : ''}</AppText>
      {onMove && player ? <SimReserveButton player={player} onOpen={onMove} /> : null}
      <SimIconButton disabled={locked} label={player ? `Change ${slotLabel}` : `Fill ${slotLabel}`} primary={!player} glyph={player ? 'trade' : 'check'} onPress={onPick} />
    </View>
  );
}
