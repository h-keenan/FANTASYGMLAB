import React, { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import PositionBadge from './PositionBadge';
import SimGlyph from './SimGlyph';
import {
  SimFold,
  SimMiniPlayer,
  SimPlayerChip,
  SimSeeAll,
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
  simProjNote,
  simFmtRecord,
  simMarginLine,
  simPlayoffStatusLabel,
  simStandingsWindow,
  type SimByeAlert,
  type SimGamePlayer,
  type SimHomeResponse,
  type SimTrendRow,
  type SimWaiverSuggestion,
} from '../lib/simGame';
import { compactCount } from '../lib/compactModule';
import { simByeParts, simInboxParts, simInjuryParts, simStandingsParts, simWaiverParts } from '../lib/simSummaries';
import type { SimTab } from '../lib/simGameFlow';
import { simPreview } from '../lib/simLayout';
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
  const [all, setAll] = useState(false);
  if (alerts.length === 0) return null;
  const uncovered = alerts.filter((a) => !a.covered).length;
  const { shown, hidden } = simPreview(alerts, all, 2);
  return (
    <SimFold
      id="home.bye"
      glyph="bye"
      tone={uncovered ? 'warning' : 'success'}
      title="Bye-week cover"
      parts={simByeParts(alerts)}
    >
      {shown.map((a) => (
        <View key={`${a.week}-${a.player.id}`} style={common.tight} testID="bye-alert">
          <View style={common.wrapRow}>
            <ToneBadge label={a.weeks_away === 0 ? 'This week' : `Week ${a.week}`} color={a.weeks_away === 0 ? colors.danger : colors.warning} size="xs" />
            <PositionBadge position={a.player.pos} label={a.pos_label} />
            <ToneBadge label={a.covered ? 'Covered' : 'Needs cover'} color={a.covered ? colors.success : colors.danger} size="xs" />
          </View>
          <SimPlayerChip player={{ ...a.player, status: 'bye' }} size={32} hidePosition quick />
          <AppText style={common.small}>{a.message}</AppText>
          {a.covered && a.covered_by ? (
            <View style={common.row}>
              <SimGlyph name="check" color={colors.success} size={14} />
              <SimMiniPlayer player={a.covered_by} onOpen={ctx.openPlayer} />
            </View>
          ) : (
            a.replacements.slice(0, all ? undefined : 1).map((r) => (
              <View key={r.id} style={common.rowBetween}>
                <View style={common.grow}>
                  <SimMiniPlayer player={r} onOpen={ctx.openPlayer} />
                </View>
                <AppText style={common.small}>{simProjNote(r) ?? `${simFmtPts(r.projection)} proj`}</AppText>
                <Button label="Claim" size="sm" onPress={() => onClaim(r)} />
              </View>
            ))
          )}
        </View>
      ))}
      <SimSeeAll hidden={hidden} expanded={all} onToggle={() => setAll((v) => !v)} />
      {uncovered ? <LinkButton label="Open the waiver wire" onPress={() => onTab('players')} /> : null}
    </SimFold>
  );
}

/** Free agents who would improve your lineup, each with the factors behind the suggestion. */
export function SimWaiverCard({ ctx, suggestions, onClaim, onTab }: { ctx: SimCtx; suggestions: SimWaiverSuggestion[]; onClaim: (p: SimGamePlayer) => void; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [all, setAll] = useState(false);
  const { shown, hidden } = simPreview(suggestions, all, 2);
  return (
    <SimFold
      id="home.waivers"
      glyph="waiver"
      tone="success"
      title="Waiver targets"
      openOnPhone={suggestions.length > 0}
      parts={simWaiverParts(suggestions)}
    >
      {suggestions.length === 0 ? (
        <AppText style={common.small}>Nothing on the wire beats your roster right now. Check back after the next games.</AppText>
      ) : (
        shown.map((s) => (
          <View key={s.player.id} style={common.tight} testID="waiver-suggestion">
            <View style={common.rowBetween}>
              <Pressable style={common.grow} onPress={() => ctx.openPlayer(s.player)} accessibilityRole="button" accessibilityLabel={`${s.player.name}, ${s.player.pos}. Open player details`}>
                <SimPlayerChip player={s.player} size={32} />
              </Pressable>
              <View style={{ alignItems: 'flex-end' }}>
                <SimTrend delta={Math.max(s.gain_now, s.gain_ros)} />
                <AppText style={common.muted}>{s.gain_now >= s.gain_ros ? 'this week' : 'per week'}</AppText>
              </View>
              <Button label="Claim" size="sm" onPress={() => onClaim(s.player)} />
            </View>
            {s.reasons.slice(0, all ? undefined : 1).map((r) => (
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
      <SimSeeAll hidden={hidden} expanded={all} onToggle={() => setAll((v) => !v)} />
      <LinkButton label="Browse every free agent" onPress={() => onTab('players')} />
    </SimFold>
  );
}

/** Trade offers waiting on you: one compact line each (who, give/get names, expiry); the Trades tab has the detail. */
export function SimInboxCard({ inbox, onTab }: { ctx?: SimCtx; inbox: SimHomeResponse['inbox']; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [all, setAll] = useState(false);
  if (!inbox || !inbox.open) return null;
  const { count, items } = inbox;
  const { shown, hidden } = simPreview(items, all, 2);
  const names = (list: SimGamePlayer[]) => list.map((p) => p.name).join(', ');
  return (
    <SimFold
      id="home.inbox"
      glyph="trade"
      tone={count ? 'accent' : 'muted'}
      title="Trade inbox"
      openOnPhone={count > 0}
      parts={simInboxParts(inbox)}
    >
      {count === 0 ? (
        <AppText style={common.small}>No offers waiting. AI managers send new ones most weeks.</AppText>
      ) : (
        shown.map((o) => (
          <View key={o.id} style={common.tight} testID="home-offer">
            <View style={common.rowBetween}>
              <SimTeamLink teamId={o.from.team_id} name={o.from.name} size={22} />
              <AppText style={common.muted}>expires wk {o.expires_week}</AppText>
            </View>
            <AppText style={common.small}>
              <AppText style={{ color: colors.danger, fontWeight: '800' }}>Give</AppText> {names(o.you_give)}
              {' · '}
              <AppText style={{ color: colors.success, fontWeight: '800' }}>Get</AppText> {names(o.you_get)}
            </AppText>
          </View>
        ))
      )}
      <SimSeeAll hidden={hidden} expanded={all} onToggle={() => setAll((v) => !v)} />
      <Button label={count ? 'Review offers' : 'Open Trades'} size="sm" variant={count ? 'primary' : 'secondary'} onPress={() => onTab('trades')} />
    </SimFold>
  );
}

/** Injured players on your roster, starters first. */
export function SimInjuriesCard({ ctx, injuries }: { ctx: SimCtx; injuries: SimHomeResponse['injuries'] }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const list = injuries ?? [];
  return (
    <SimFold
      id="home.injuries"
      glyph="injury"
      tone={list.length ? 'danger' : 'muted'}
      title="Injury report"
      parts={simInjuryParts(list)}
    >
      {list.length === 0 ? (
        <View style={common.row}>
          <SimGlyph name="check" color={colors.success} size={14} />
          <AppText style={[common.small, { color: colors.success }]}>Everyone on your roster is healthy.</AppText>
        </View>
      ) : (
        list.map((i) => (
          <View key={i.player.id} style={common.rowBetween} testID="home-injury">
            <Pressable style={common.grow} onPress={() => ctx.openPlayer(i.player)} accessibilityRole="button" accessibilityLabel={`${i.player.name}, ${i.player.pos}. Open player details`}>
              <SimPlayerChip player={i.player} size={28} />
            </Pressable>
            <View style={{ alignItems: 'flex-end', gap: 2 }}>
              <SimToneBadge label={`Out ${i.out_weeks} wk`} tone="danger" />
              <AppText style={[common.muted, i.starting && { color: colors.warning }]}>{i.starting ? 'In your lineup' : i.note}</AppText>
            </View>
          </View>
        ))
      )}
    </SimFold>
  );
}

/** Where you sit and the playoff cut line: the six rows around the cut. */
export function SimStandingsCard({ standings, onTab }: { standings: SimHomeResponse['standings']; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!standings) return null;
  const rows = simStandingsWindow(standings.rows, 6);
  const margin = simMarginLine(standings);
  const accent = standings.in_playoffs ? colors.success : colors.warning;
  return (
    <SimFold
      id="home.standings"
      glyph="standings"
      tone={standings.in_playoffs ? 'success' : 'warning'}
      title="Playoff picture"
      openOnPhone
      parts={simStandingsParts(standings)}
    >
      {margin ? <AppText style={[common.small, { fontWeight: '800', color: standings.margin != null && standings.margin >= 0 ? colors.success : colors.danger }]}>{margin}</AppText> : null}
      <View accessibilityLabel="Standings snapshot">
        {rows.map((r) => {
          const cut = r.rank === standings.playoff_spots;
          return (
            <View
              key={r.team_id}
              accessibilityHint={simPlayoffStatusLabel(r.playoff_status) || undefined}
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
    </SimFold>
  );
}

/** Your hottest and coldest players, and who is hot on the wire (swipeable strips). */
export function SimHotColdCard({ ctx, hotCold, onClaim }: { ctx: SimCtx; hotCold: SimHomeResponse['hot_cold']; onClaim: (p: SimGamePlayer) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!hotCold) return null;
  const { hot, cold, wire } = hotCold;
  if (hot.length + cold.length + wire.length === 0) return null;
  const strip = (list: SimTrendRow[], glyph: 'hot' | 'cold' | 'waiver', title: string, tone: 'danger' | 'accent' | 'success', claim = false) =>
    list.length === 0 ? null : (
      <View style={common.tight} key={title}>
        <SimSectionTitle glyph={glyph} tone={tone} title={title} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} accessibilityLabel={title}>
          {list.map((t) => (
            <View key={t.player.id} style={styles.trendCard} testID="trend-row">
              <SimMiniPlayer player={t.player} onOpen={ctx.openPlayer} size={24} />
              <View style={common.rowBetween}>
                <AppText style={common.bodyStrong}>{simFmtPts(t.last_week)}</AppText>
                <SimTrend delta={t.delta} />
              </View>
              {claim ? <Button label="Claim" size="sm" variant="secondary" onPress={() => onClaim(t.player)} /> : null}
            </View>
          ))}
        </ScrollView>
      </View>
    );
  return (
    <SimFold id="home.hotcold" glyph="hot" tone="danger" title="Hot and cold" parts={[{ key: 'hot', text: `${hot.length} hot`, tone: 'danger' }, { key: 'cold', text: `${cold.length} cold`, tone: 'accent' }, { key: 'wire', text: wire.length ? `${wire.length} on the wire` : '' }]}>
      {strip(hot, 'hot', 'Heating up', 'danger')}
      {strip(cold, 'cold', 'Cooling off', 'accent')}
      {strip(wire, 'waiver', 'Hot on the wire', 'success', true)}
    </SimFold>
  );
}

/** The most interesting trade this week, then the latest moves around the league. */
export function SimLeagueMovesCard({ league, names, onTab }: { league: SimHomeResponse['league']; names: Record<string, string>; onTab: OnTab }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [all, setAll] = useState(false);
  if (!league) return null;
  const spot = league.spotlight;
  if (!spot && league.recent.length === 0) return null;
  const { shown, hidden } = simPreview(league.recent, all, 3);
  return (
    <SimFold id="home.league" glyph="league" tone="accent" title="Around the league" openOnPhone={Boolean(spot)} parts={[spot ? { key: 'spot', text: 'Trade to know', tone: 'accent', strong: true } : null, { key: 'mv', text: compactCount(league.recent.length, 'move'), tone: 'muted' }]}>
      {spot ? (
        <View style={styles.spot} testID="trade-spotlight">
          <View style={common.row}>
            <SimGlyph name="spark" color={colors.premium} size={14} />
            <ToneBadge label="Trade to know" color={colors.premium} size="xs" />
            <AppText style={common.muted}>Week {spot.week}</AppText>
          </View>
          <View style={styles.spotTeams}>
            <SimTeamLink teamId={spot.team_a.team_id} name={spot.team_a.name} isYou={spot.team_a.is_you} size={28} stacked />
            <SimGlyph name="trade" color={colors.textSecondary} size={18} />
            <SimTeamLink teamId={spot.team_b.team_id} name={spot.team_b.name} isYou={spot.team_b.is_you} size={28} stacked />
          </View>
          <AppText style={common.bodyStrong}>{spot.headline}</AppText>
          <AppText style={common.small}>{spot.text}</AppText>
          <View style={common.wrapRow}>
            {spot.players.map((p) => (
              <View key={`${p.role}-${p.id}`} style={common.row}>
                <ToneBadge label={p.role} color={p.role === 'get' ? colors.success : colors.textTertiary} size="xs" />
                <SimPlayerChip player={p} size={24} quick />
              </View>
            ))}
          </View>
        </View>
      ) : null}
      {shown.map((m, i) => (
        <View key={i} style={[common.row, i > 0 && common.divider, { alignItems: 'flex-start', paddingVertical: spacing.xs }]}>
          <SimTeamLink teamId={m.team_id} name={names[m.team_id] ?? 'Team'} size={22} hideName />
          <AppText style={[common.small, common.grow]}>{m.text}</AppText>
          <ToneBadge label={`Wk ${m.week}`} color={simToneColor('muted', colors)} size="xs" />
        </View>
      ))}
      <SimSeeAll hidden={hidden} expanded={all} onToggle={() => setAll((v) => !v)} />
      <LinkButton label="See the full feed" onPress={() => onTab('league')} />
    </SimFold>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: 4 },
    stRank: { width: 20, fontSize: 13, fontWeight: '800' },
    spot: { gap: spacing.sm, padding: spacing.sm, borderRadius: radii.md, backgroundColor: colors.premiumMuted },
    spotTeams: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', gap: spacing.sm },
    strip: { gap: spacing.sm, paddingBottom: 2 },
    trendCard: { width: 144, gap: 4, padding: spacing.sm, borderRadius: radii.md, borderWidth: 1, borderColor: colors.border },
  });
}
