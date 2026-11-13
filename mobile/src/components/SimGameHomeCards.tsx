import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import PositionBadge from './PositionBadge';
import SimGlyph from './SimGlyph';
import {
  SimMiniPlayer,
  SimPlayerChip,
  SimSectionTitle,
  SimTeamLink,
  SimToneBadge,
  SimTrend,
  createSimStyles,
  simToneColor,
  type SimCtx,
} from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  simFmtPts,
  simFmtRecord,
  simMarginLine,
  simStandingsWindow,
  type SimByeAlert,
  type SimGamePlayer,
  type SimHomeResponse,
  type SimWaiverSuggestion,
} from '../lib/simGame';
import type { SimTab } from '../lib/simGameFlow';
import { radii, spacing, type ThemeColors } from '../theme';

type OnTab = (tab: SimTab) => void;

function LinkButton({ label, onPress }: { label: string; onPress: () => void }) {
  const { colors } = useThemeMode();
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={{ minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' }}>
      <AppText style={{ fontSize: 13, fontWeight: '800', color: colors.accent }}>{label}</AppText>
    </Pressable>
  );
}

/** Upcoming byes that leave a starter hole, with the bench cover or free agents to claim. */
export function SimByeCard({ ctx, alerts, onTab, onClaim }: { ctx: SimCtx; alerts: SimByeAlert[]; onTab: OnTab; onClaim: (p: SimGamePlayer) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  if (alerts.length === 0) return null;
  const uncovered = alerts.filter((a) => !a.covered).length;
  return (
    <AccentCard accent={uncovered ? colors.warning : colors.success}>
      <SimSectionTitle glyph="bye" tone={uncovered ? 'warning' : 'success'} title="Bye-week cover" caption="Starters whose NFL team is off in the next few weeks." />
      {alerts.map((a) => (
        <View key={`${a.week}-${a.player.id}`} style={common.tight} testID="bye-alert">
          <View style={common.wrapRow}>
            <ToneBadge label={a.weeks_away === 0 ? 'This week' : `Week ${a.week}`} color={a.weeks_away === 0 ? colors.danger : colors.warning} size="xs" />
            <PositionBadge position={a.player.pos} label={a.pos_label} />
            <ToneBadge label={a.covered ? 'Covered' : 'Needs cover'} color={a.covered ? colors.success : colors.danger} size="xs" />
          </View>
          <SimPlayerChip player={{ ...a.player, status: 'bye' }} size={32} hidePosition />
          <AppText style={common.small}>{a.message}</AppText>
          {a.covered && a.covered_by ? (
            <View style={common.row}>
              <SimGlyph name="check" color={colors.success} size={14} />
              <SimMiniPlayer player={a.covered_by} onOpen={ctx.openPlayer} />
            </View>
          ) : (
            a.replacements.map((r) => (
              <View key={r.id} style={common.rowBetween}>
                <View style={common.grow}>
                  <SimMiniPlayer player={r} onOpen={ctx.openPlayer} />
                </View>
                <AppText style={common.small}>{simFmtPts(r.projection)} proj</AppText>
                <Button label="Claim" size="sm" onPress={() => onClaim(r)} />
              </View>
            ))
          )}
        </View>
      ))}
      {uncovered ? <LinkButton label="Open the waiver wire" onPress={() => onTab('players')} /> : null}
    </AccentCard>
  );
}

/** Free agents who would improve your lineup, each with the factors behind the suggestion. */
export function SimWaiverCard({ ctx, suggestions, onClaim, onTab }: { ctx: SimCtx; suggestions: SimWaiverSuggestion[]; onClaim: (p: SimGamePlayer) => void; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <AccentCard accent={colors.success}>
      <SimSectionTitle glyph="waiver" tone="success" title="Waiver targets" caption="Free agents that fix a hole or upgrade a starter." />
      {suggestions.length === 0 ? (
        <AppText style={common.small}>Nothing on the wire beats your roster right now. Check back after the next games.</AppText>
      ) : (
        suggestions.map((s) => (
          <View key={s.player.id} style={common.tight} testID="waiver-suggestion">
            <View style={common.rowBetween}>
              <Pressable style={common.grow} onPress={() => ctx.openPlayer(s.player)} accessibilityRole="button" accessibilityLabel={`${s.player.name}, ${s.player.pos}. Open player details`}>
                <SimPlayerChip player={s.player} size={36} />
              </Pressable>
              <View style={{ alignItems: 'flex-end' }}>
                <SimTrend delta={Math.max(s.gain_now, s.gain_ros)} />
                <AppText style={common.muted}>{s.gain_now >= s.gain_ros ? 'this week' : 'per week'}</AppText>
              </View>
              <Button label="Claim" size="sm" onPress={() => onClaim(s.player)} />
            </View>
            {s.reasons.map((r) => (
              <AppText key={r} style={common.small}>
                <AppText style={{ color: colors.success, fontWeight: '800' }}>+ </AppText>
                {r}
              </AppText>
            ))}
            {s.drop ? (
              <AppText style={common.muted}>
                <AppText style={{ color: colors.danger, fontWeight: '800' }}>- </AppText>
                Your roster is full: drop {s.drop.name} ({s.drop.pos})
              </AppText>
            ) : null}
          </View>
        ))
      )}
      <LinkButton label="Browse every free agent" onPress={() => onTab('players')} />
    </AccentCard>
  );
}

/** Trade offers waiting on you, with the badge count. */
export function SimInboxCard({ ctx, inbox, onTab }: { ctx: SimCtx; inbox: SimHomeResponse['inbox']; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  if (!inbox || !inbox.open) return null;
  const { count, items } = inbox;
  return (
    <AccentCard accent={count ? colors.accent : colors.borderStrong}>
      <SimSectionTitle glyph="trade" tone={count ? 'accent' : 'muted'} title="Trade inbox" right={count ? <ToneBadge label={`${count} new`} color={colors.accent} /> : undefined} />
      {count === 0 ? (
        <AppText style={common.small}>No offers waiting. AI managers send new ones most weeks.</AppText>
      ) : (
        items.map((o) => (
          <View key={o.id} style={common.tight}>
            <View style={common.rowBetween}>
              <SimTeamLink teamId={o.from.team_id} name={o.from.name} size={28} />
              <AppText style={common.muted}>expires wk {o.expires_week}</AppText>
            </View>
            <View style={common.row}>
              <View style={common.grow}>
                <AppText style={{ fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.danger }}>YOU GIVE</AppText>
                {o.you_give.map((p) => (
                  <SimMiniPlayer key={p.id} player={p} onOpen={ctx.openPlayer} size={24} />
                ))}
              </View>
              <View style={common.grow}>
                <AppText style={{ fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.success }}>YOU GET</AppText>
                {o.you_get.map((p) => (
                  <SimMiniPlayer key={p.id} player={p} onOpen={ctx.openPlayer} size={24} />
                ))}
              </View>
            </View>
          </View>
        ))
      )}
      <Button label={count ? 'Review offers' : 'Open Trades'} size="sm" variant={count ? 'primary' : 'secondary'} onPress={() => onTab('trades')} />
    </AccentCard>
  );
}

/** Injured players on your roster, starters first. */
export function SimInjuriesCard({ ctx, injuries }: { ctx: SimCtx; injuries: SimHomeResponse['injuries'] }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const list = injuries ?? [];
  return (
    <AccentCard accent={list.some((i) => i.starting) ? colors.danger : colors.borderStrong}>
      <SimSectionTitle glyph="injury" tone={list.length ? 'danger' : 'muted'} title="Injury report" />
      {list.length === 0 ? (
        <View style={common.row}>
          <SimGlyph name="check" color={colors.success} size={14} />
          <AppText style={[common.small, { color: colors.success }]}>Everyone on your roster is healthy.</AppText>
        </View>
      ) : (
        list.map((i) => (
          <View key={i.player.id} style={common.rowBetween} testID="home-injury">
            <Pressable style={common.grow} onPress={() => ctx.openPlayer(i.player)} accessibilityRole="button" accessibilityLabel={`${i.player.name}, ${i.player.pos}. Open player details`}>
              <SimPlayerChip player={i.player} size={36} />
            </Pressable>
            <View style={{ alignItems: 'flex-end', gap: 2 }}>
              <SimToneBadge label={`Out ${i.out_weeks} wk`} tone="danger" />
              <AppText style={[common.muted, i.starting && { color: colors.warning }]}>{i.starting ? 'In your lineup' : i.note}</AppText>
            </View>
          </View>
        ))
      )}
    </AccentCard>
  );
}

/** Where you sit and the playoff cut line. */
export function SimStandingsCard({ standings, onTab }: { standings: SimHomeResponse['standings']; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!standings) return null;
  const rows = simStandingsWindow(standings.rows, 6);
  const margin = simMarginLine(standings);
  const accent = standings.in_playoffs ? colors.success : colors.warning;
  return (
    <AccentCard accent={accent}>
      <SimSectionTitle glyph="standings" tone={standings.in_playoffs ? 'success' : 'warning'} title="Playoff picture" right={<ToneBadge label={standings.in_playoffs ? 'In the playoffs' : 'Outside'} color={accent} />} />
      {margin ? <AppText style={[common.small, { fontWeight: '800', color: standings.margin != null && standings.margin >= 0 ? colors.success : colors.danger }]}>{margin}</AppText> : null}
      <View accessibilityLabel="Standings snapshot">
        {rows.map((r) => {
          const cut = r.rank === standings.playoff_spots;
          return (
            <View
              key={r.team_id}
              style={[
                styles.stRow,
                r.is_you && { backgroundColor: colors.accentMuted },
                cut ? { borderBottomWidth: 2, borderStyle: 'dashed', borderBottomColor: colors.success } : { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
              ]}
            >
              <AppText style={[styles.stRank, { color: r.rank <= standings.playoff_spots ? colors.success : colors.textTertiary }]}>{r.rank}</AppText>
              <View style={common.grow}>
                <SimTeamLink teamId={r.team_id} name={r.name} isYou={r.is_you} size={22} bold={r.is_you} />
              </View>
              <AppText style={[common.small, { color: r.streak?.startsWith('W') ? colors.success : r.streak?.startsWith('L') ? colors.danger : colors.textTertiary }]}>{r.streak ?? ''}</AppText>
              <AppText style={common.bodyStrong}>{simFmtRecord(r)}</AppText>
            </View>
          );
        })}
      </View>
      <AppText style={common.muted}>Dashed line: top {standings.playoff_spots} make the playoffs.</AppText>
      <LinkButton label="Full standings" onPress={() => onTab('league')} />
    </AccentCard>
  );
}

/** Your hottest and coldest players, and who is hot on the wire. */
export function SimHotColdCard({ ctx, hotCold, onClaim }: { ctx: SimCtx; hotCold: SimHomeResponse['hot_cold']; onClaim: (p: SimGamePlayer) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  if (!hotCold) return null;
  const { hot, cold, wire } = hotCold;
  if (hot.length + cold.length + wire.length === 0) return null;
  const rows = (list: typeof hot, glyph: 'hot' | 'cold' | 'waiver', title: string, tone: 'danger' | 'accent' | 'success', claim = false) =>
    list.length === 0 ? null : (
      <View style={common.tight} key={title}>
        <SimSectionTitle glyph={glyph} tone={tone} title={title} />
        {list.map((t) => (
          <View key={t.player.id} style={common.rowBetween} testID="trend-row">
            <View style={common.grow}>
              <SimMiniPlayer player={t.player} onOpen={ctx.openPlayer} size={30} />
            </View>
            <AppText style={common.bodyStrong}>{simFmtPts(t.last_week)} pts</AppText>
            <SimTrend delta={t.delta} suffix=" vs proj" />
            {claim ? <Button label="Claim" size="sm" variant="secondary" onPress={() => onClaim(t.player)} /> : null}
          </View>
        ))}
      </View>
    );
  return (
    <AccentCard accent={colors.premium}>
      <SimSectionTitle glyph="hot" tone="danger" title="Hot and cold" caption="Last week against what we projected." />
      {rows(hot, 'hot', 'Heating up', 'danger')}
      {rows(cold, 'cold', 'Cooling off', 'accent')}
      {rows(wire, 'waiver', 'Hot on the wire', 'success', true)}
    </AccentCard>
  );
}

/** The most interesting trade this week, then the latest moves around the league. */
export function SimLeagueMovesCard({ league, names, onTab }: { league: SimHomeResponse['league']; names: Record<string, string>; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!league) return null;
  const spot = league.spotlight;
  if (!spot && league.recent.length === 0) return null;
  return (
    <AccentCard accent={colors.premium}>
      <SimSectionTitle glyph="league" title="Around the league" caption="What the other managers did lately." />
      {spot ? (
        <View style={styles.spot} testID="trade-spotlight">
          <View style={common.row}>
            <SimGlyph name="spark" color={colors.premium} size={14} />
            <ToneBadge label="Trade to know" color={colors.premium} size="xs" />
            <AppText style={common.muted}>Week {spot.week}</AppText>
          </View>
          <View style={styles.spotTeams}>
            <SimTeamLink teamId={spot.team_a.team_id} name={spot.team_a.name} isYou={spot.team_a.is_you} size={32} stacked />
            <SimGlyph name="trade" color={colors.textSecondary} size={18} />
            <SimTeamLink teamId={spot.team_b.team_id} name={spot.team_b.name} isYou={spot.team_b.is_you} size={32} stacked />
          </View>
          <AppText style={common.bodyStrong}>{spot.headline}</AppText>
          <AppText style={common.small}>{spot.text}</AppText>
          {spot.players.map((p) => (
            <View key={`${p.role}-${p.id}`} style={common.row}>
              <ToneBadge label={p.role} color={p.role === 'get' ? colors.success : colors.textTertiary} size="xs" />
              <SimPlayerChip player={p} size={24} />
            </View>
          ))}
        </View>
      ) : null}
      {league.recent.map((m, i) => (
        <View key={i} style={[common.row, i > 0 && common.divider, { alignItems: 'flex-start', paddingVertical: spacing.xs }]}>
          <SimTeamLink teamId={m.team_id} name={names[m.team_id] ?? 'Team'} size={22} hideName />
          <AppText style={[common.small, common.grow]}>{m.text}</AppText>
          <ToneBadge label={`Wk ${m.week}`} color={simToneColor('muted', colors)} size="xs" />
        </View>
      ))}
      <LinkButton label="See the full feed" onPress={() => onTab('league')} />
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: 4 },
    stRank: { width: 20, fontSize: 13, fontWeight: '800' },
    spot: { gap: spacing.sm, padding: spacing.sm, borderRadius: radii.md, backgroundColor: colors.premiumMuted },
    spotTeams: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', gap: spacing.sm },
  });
}
