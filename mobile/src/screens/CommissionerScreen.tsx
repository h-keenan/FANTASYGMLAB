import TeamNameLink from '../components/TeamNameLink';
import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import PressableScale from '../components/PressableScale';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useHeaderHeight } from '@react-navigation/elements';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AccentCard from '../components/AccentCard';
import { ExpandRow, ExpandRowGroup } from '../components/ExpandRow';
import { Collapse } from '../components/Presence';
import InfoMark from '../components/InfoMark';
import TeamAvatar from '../components/TeamAvatar';
import AppText from '../components/AppText';
import { SkeletonList } from '../components/Skeleton';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import LineupCheck from '../components/LineupCheck';
import IconRow, { type IconRowIcon } from '../components/IconRow';
import MetricCard from '../components/MetricCard';
import PremiumLock from '../components/PremiumLock';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import ToneBadge from '../components/ToneBadge';
import VetoCalculator from '../components/VetoCalculator';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { api } from '../lib/api';
import {
  BAND_LABEL,
  bandTone,
  CONFIDENCE_LABEL,
  DRAFT_ORDER_OPTIONS,
  INTERPRETATION_LABEL,
  calendarLines,
  integrityReasonMessage,
  integritySummaryLine,
  INTEGRITY_CAVEAT,
  weeksFlaggedLine,
  restSummary,
  splitTeams,
  type CommissionerIntegrityResponse,
  type IntegrityCalendar,
  type DraftOrderRule,
  type IntegrityBand,
  type IntegrityCollusionPair,
  type IntegrityInactiveManager,
  type IntegrityTeam,
} from '../lib/commissionerIntegrity';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Commissioner'>;

/**
 * Commissioner: league integrity (lineups, tanking signals, lopsided repeat
 * trades, inactive managers) for any Pro user who can open the league (no
 * commissioner check). Every number is read from the server (modules/league_integrity.py); signals are prompts to
 * look, so each card lists the innocent explanations beside the evidence.
 * Mirrors web-next's CommissionerContent and shares lib/commissionerIntegrity.
 */
export default function CommissionerScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { lens } = useValuationLens(leagueId);
  const queryClient = useQueryClient();
  // The saved rule (per user + league, server-side). Until it resolves the integrity read waits, so the first request already uses the saved rule.
  const ruleQuery = useQuery({
    queryKey: queryKeys.draftOrderRule(leagueId),
    queryFn: async () => (await api.getDraftOrderRule(leagueId)).draft_order ?? 'unknown',
    staleTime: 5 * 60 * 1000,
  });
  const ruleReady = ruleQuery.isSuccess || ruleQuery.isError;
  const draftOrder: DraftOrderRule = ruleQuery.data ?? 'unknown';
  // Changing it saves server-side and re-keys the integrity read (a refetch with the new rule).
  const setDraftOrder = (value: DraftOrderRule) => {
    const previous = queryClient.getQueryData<DraftOrderRule>(queryKeys.draftOrderRule(leagueId));
    queryClient.setQueryData(queryKeys.draftOrderRule(leagueId), value);
    // A failed save must not leave the screen showing a rule the server never stored.
    api.setDraftOrderRule(leagueId, value).catch(() => {
      if (queryClient.getQueryData(queryKeys.draftOrderRule(leagueId)) === value) {
        queryClient.setQueryData(queryKeys.draftOrderRule(leagueId), previous ?? 'unknown');
      }
    });
  };
  useScreenHeaderTitle(navigation, 'Commissioner', leagueName);

  const query = useQuery({
    queryKey: queryKeys.commissionerIntegrity(leagueId, draftOrder),
    queryFn: () => api.getCommissionerIntegrity(leagueId, draftOrder),
    enabled: ruleReady,
    staleTime: 5 * 60 * 1000,
  });
  const data = query.data;

  const toneColor = (band: IntegrityBand): string => {
    const tone = bandTone(band);
    return tone === 'success' ? colors.success : tone === 'warning' ? colors.warning : tone === 'danger' ? colors.danger : colors.textTertiary;
  };

  let body: React.ReactNode;
  if (!ruleReady || query.isLoading) {
    body = <SkeletonList label="league integrity" count={5} />;
  } else if (query.error || !data) {
    body = <ErrorState title="Couldn't load League integrity" message={toUserErrorMessage(query.error, 'Failed to load League integrity.')} />;
  } else if (data.is_premium === false) {
    body = (
      <PremiumLock
        feature="commissioner"
        leagueName={leagueName}
        title={data.upsell?.title || 'Spot tanking and lineup problems early'}
        description={data.upsell?.body || 'League integrity is a Pro feature: lineup efficiency, tanking signals with the evidence behind them, repeated lopsided trades and inactive managers.'}
      />
    );
  } else if (data.reason) {
    body = (
      <View style={styles.stack}>
        <EmptyState icon="shield-checkmark-outline" title="Nothing to show yet" subtitle={integrityReasonMessage(data.reason)} />
        <CalendarCard calendar={data.calendar} accent={colors.accent} styles={styles} />
      </View>
    );
  } else {
    body = <IntegrityBody leagueId={leagueId} leagueName={leagueName} data={data} draftOrder={draftOrder} onDraftOrder={setDraftOrder} toneColor={toneColor} styles={styles} />;
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        {body}
        {data && !query.isLoading && data.is_premium !== false ? <LineupCheck leagueId={leagueId} leagueName={leagueName} lens={lens} /> : null}
        {data && !query.isLoading && data.is_premium !== false ? <VetoCalculator leagueId={leagueId} lens={lens} /> : null}
      </ScrollView>
    </View>
  );
}

/** A titled group of icon rows (evidence / innocent explanations). */
function Bullets({
  title,
  items,
  styles,
  icon = 'info',
  color,
}: {
  title: string;
  items: string[];
  styles: ReturnType<typeof createStyles>;
  icon?: IconRowIcon;
  color?: string;
}) {
  if (!items.length) return null;
  return (
    <View style={styles.bullets}>
      <AppText style={[styles.bulletsTitle, color ? { color } : null]}>{title}</AppText>
      {items.map((text) => (
        <IconRow key={text} icon={icon} color={color}>
          {text}
        </IconRow>
      ))}
    </View>
  );
}

function EfficiencyBars({ team, colors, styles }: { team: IntegrityTeam; colors: ThemeColors; styles: ReturnType<typeof createStyles> }) {
  if (!team.series.length) return null;
  return (
    <View style={styles.bullets}>
      <AppText style={styles.bulletsTitle}>Lineup efficiency by week</AppText>
      <View style={styles.bars} accessibilityLabel="Lineup efficiency by week">
        {team.series.map((point) => {
          const pct = Math.max(0.05, Math.min(1, point.efficiency ?? 0));
          return (
            <View key={point.week} style={styles.barCol}>
              <View
                style={{
                  width: '100%',
                  height: Math.round(pct * 40),
                  borderRadius: 2,
                  backgroundColor: point.flagged ? colors.warning : colors.success,
                  opacity: point.flagged ? 1 : 0.55,
                }}
              />
              <AppText style={styles.barLabel}>{point.week}</AppText>
            </View>
          );
        })}
      </View>
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: colors.success, opacity: 0.55 }]} />
          <AppText style={styles.barLabel}>Normal week</AppText>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: colors.warning }]} />
          <AppText style={styles.barLabel}>Flagged week</AppText>
        </View>
      </View>
    </View>
  );
}

/** The grouped surface every flagged-item list shares (one card, hairline dividers, one row per team or pair). */
function IntegrityRows({ children, accent, testID }: { children: React.ReactNode; accent: string; testID?: string }) {
  return (
    <ExpandRowGroup accent={accent} testID={testID}>
      {children}
    </ExpandRowGroup>
  );
}

/** One team: avatar, name, "n of m weeks flagged", a band badge; tapping opens the evidence, the weekly bars and the innocent explanations. */
function TeamRow({
  leagueId,
  leagueName,
  team,
  toneColor,
  colors,
  styles,
}: {
  leagueId: string;
  leagueName: string;
  team: IntegrityTeam;
  toneColor: (band: IntegrityBand) => string;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
}) {
  const expandable = team.band === 'strong' || team.band === 'worth_a_look';
  const interpretation = INTERPRETATION_LABEL[team.interpretation];
  const caption = [team.owner_name, weeksFlaggedLine(team)].filter(Boolean).join(' · ');
  return (
    <ExpandRow
      testID={`integrity-team-${team.roster_id}`}
      label={`${team.team_name}, ${BAND_LABEL[team.band]}`}
      // team-tap-exempt: the whole row is one expand toggle; the team sheet opens from the "Open team" link inside it
      leading={<TeamAvatar avatarId={team.avatar_url} name={team.team_name} size={32} />}
      title={team.team_name}
      caption={caption || undefined}
      chips={expandable && interpretation ? <ToneBadge label={`${interpretation} · ${CONFIDENCE_LABEL[team.confidence]}`} color={colors.textTertiary} /> : undefined}
      action={<ToneBadge label={BAND_LABEL[team.band]} color={toneColor(team.band)} />}
      defaultOpen={team.band === 'strong'}
    >
      {expandable ? (
        <>
          <TeamNameLink leagueId={leagueId} leagueName={leagueName} rosterId={team.roster_id} name={team.team_name} ownerName={team.owner_name} avatarId={team.avatar_url} textStyle={styles.teamLink}>
            Open team
          </TeamNameLink>
          <Bullets title="Evidence" items={team.evidence.map((e) => e.text)} styles={styles} icon="alert" color={toneColor(team.band)} />
          <EfficiencyBars team={team} colors={colors} styles={styles} />
          <Bullets title="Could be innocent" items={team.innocent_explanations} styles={styles} icon="info" color={colors.accent} />
        </>
      ) : null}
    </ExpandRow>
  );
}

function IntegrityBody({
  leagueId,
  leagueName,
  data,
  draftOrder,
  onDraftOrder,
  toneColor,
  styles,
}: {
  leagueId: string;
  leagueName: string;
  data: CommissionerIntegrityResponse;
  draftOrder: DraftOrderRule;
  onDraftOrder: (value: DraftOrderRule) => void;
  toneColor: (band: IntegrityBand) => string;
  styles: ReturnType<typeof createStyles>;
}) {
  const { colors } = useThemeMode();
  const { flagged, rest } = splitTeams(data.teams);
  const [showRest, setShowRest] = useState(false);
  return (
    <View style={styles.stack}>
      <View style={styles.summaryRow}>
        <AppText style={[styles.body, styles.flex]}>{integritySummaryLine(data)}</AppText>
        <InfoMark label="what this can and can't tell you" lines={[INTEGRITY_CAVEAT, ...(data.limits ?? [])]} />
      </View>
      <CalendarCard calendar={data.calendar} accent={colors.accent} styles={styles} />
      <View style={styles.bullets}>
        <View style={styles.summaryRow}>
          <AppText style={styles.bulletsTitle}>How is your draft order set?</AppText>
          <InfoMark
            label="the draft order rule"
            lines={['Worst record means the worst team picks first; Lottery covers any other order. Sleeper does not publish this, so it changes how a flagged team is described, not the lineup math.']}
          />
        </View>
        <SegmentedTabBar
          options={DRAFT_ORDER_OPTIONS.map((o) => ({ key: o.value, label: o.label }))}
          active={draftOrder}
          onChange={onDraftOrder}
        />
      </View>

      {flagged.length ? (
        <View style={styles.stack}>
          <SectionHeading title="Worth a look" />
          <IntegrityRows accent={colors.warning} testID="integrity-flagged">
            {flagged.map((team) => (
              <TeamRow key={team.roster_id} leagueId={leagueId} leagueName={leagueName} team={team} toneColor={toneColor} colors={colors} styles={styles} />
            ))}
          </IntegrityRows>
        </View>
      ) : null}

      {data.collusion.length ? (
        <View style={styles.stack}>
          <SectionHeading
            title="Repeated trades worth a look"
            info={
              <InfoMark
                label="repeated trades"
                lines={['Same two managers, repeated trades: one-sided on value (picks priced like the Trade Analyzer), assets going back and forth, or several trades in one week. A prompt to look, not a verdict.']}
              />
            }
          />
          <IntegrityRows accent={colors.warning} testID="integrity-collusion">
            {data.collusion.map((pair) => (
              <CollusionRow key={pair.roster_ids.join('-')} pair={pair} teams={data.teams} toneColor={toneColor} accent={colors.accent} styles={styles} />
            ))}
          </IntegrityRows>
        </View>
      ) : null}

      {data.inactive.length ? (
        <View style={styles.stack}>
          <SectionHeading title="Possibly inactive" />
          <IntegrityRows accent={colors.warning} testID="integrity-inactive">
            {data.inactive.map((m) => (
              <InactiveRow key={m.roster_id} leagueId={leagueId} leagueName={leagueName} manager={m} teams={data.teams} accent={colors.warning} infoColor={colors.accent} styles={styles} />
            ))}
          </IntegrityRows>
        </View>
      ) : null}

      {rest.length ? (
        <View style={styles.stack}>
          <SectionHeading title={flagged.length ? 'Everyone else' : 'Team lineups'} />
          <AccentCard accent={colors.success}>
            <View style={styles.cardHead}>
              <View style={styles.flex}>
                <IconRow icon="check" color={colors.success} textStyle={[styles.teamName, { color: colors.success }]}>
                  {restSummary(data.teams, flagged.length)}
                </IconRow>
              </View>
              <PressableScale onPress={() => setShowRest((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: showRest }}>
                <AppText style={styles.link}>{showRest ? 'Hide teams' : `Show ${rest.length} team${rest.length === 1 ? '' : 's'}`}</AppText>
              </PressableScale>
            </View>
          </AccentCard>
          <Collapse open={showRest}>
            <IntegrityRows accent={colors.success} testID="integrity-rest">
              {rest.map((team) => (
                <TeamRow key={team.roster_id} leagueId={leagueId} leagueName={leagueName} team={team} toneColor={toneColor} colors={colors} styles={styles} />
              ))}
            </IntegrityRows>
          </Collapse>
        </View>
      ) : null}
    </View>
  );
}

function CalendarCard({
  calendar,
  accent,
  styles,
}: {
  calendar: IntegrityCalendar | null | undefined;
  accent: string;
  styles: ReturnType<typeof createStyles>;
}) {
  const { colors } = useThemeMode();
  if (!calendarLines(calendar).length || !calendar) return null;
  const d = calendar.trade_deadline_week;
  const deadlineNote =
    d == null
      ? 'No deadline set'
      : calendar.deadline_phase === 'passed'
        ? 'Passed; reopens after the season'
        : calendar.deadline_phase === 'final_week'
          ? 'This week: last call'
          : calendar.weeks_to_deadline != null
            ? `${calendar.weeks_to_deadline} week${calendar.weeks_to_deadline === 1 ? '' : 's'} left`
            : null;
  const season = calendar.regular_season_weeks;
  const progress =
    calendar.in_season && calendar.current_week && season
      ? Math.max(0, Math.min(100, Math.round((calendar.current_week / season) * 100)))
      : null;
  return (
    <View style={styles.bullets}>
      <SectionHeading title="League calendar" />
      <View style={styles.tileRow}>
        {calendar.current_week && calendar.in_season ? (
          <MetricCard style={styles.tile} icon="calendar-outline" label="Now" value={`Wk ${calendar.current_week}`} note={season ? `of ${season}` : null} />
        ) : null}
        <MetricCard
          style={styles.tile}
          icon="flag-outline"
          label="Trade deadline"
          value={d == null ? 'None' : `Wk ${d}`}
          note={deadlineNote}
          valueColor={calendar.deadline_phase === 'final_week' ? colors.warning : undefined}
        />
        {calendar.playoff_week_start ? (
          <MetricCard style={styles.tile} icon="trophy-outline" label="Playoffs" value={`Wk ${calendar.playoff_week_start}`} note="Start" />
        ) : null}
      </View>
      {progress !== null ? (
        <View
          style={styles.progressTrack}
          accessibilityRole="progressbar"
          accessibilityLabel="Regular season progress"
          accessibilityValue={{ min: 0, max: 100, now: progress }}
        >
          <View style={[styles.progressFill, { width: `${progress}%`, backgroundColor: accent }]} />
        </View>
      ) : null}
    </View>
  );
}

/** Both teams of a repeated-trade pair, overlapped (a team missing from the list falls back to initials). */
function PairAvatars({ pair, teams }: { pair: IntegrityCollusionPair; teams: IntegrityTeam[] }) {
  const names = [pair.beneficiary_name, pair.giver_name];
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      {pair.roster_ids.slice(0, 2).map((rid, i) => {
        const t = teams.find((x) => x.roster_id === rid);
        return (
          <View key={rid} style={{ marginLeft: i ? -10 : 0 }}>
            {/* team-tap-exempt: decorative mark inside the row's expand toggle */}
            <TeamAvatar avatarId={t?.avatar_url} name={t?.team_name ?? names[i]} size={28} />
          </View>
        );
      })}
    </View>
  );
}

function CollusionRow({
  pair,
  teams,
  toneColor,
  accent,
  styles,
}: {
  pair: IntegrityCollusionPair;
  teams: IntegrityTeam[];
  toneColor: (band: IntegrityBand) => string;
  accent: string;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <ExpandRow
      testID={`integrity-pair-${pair.roster_ids.join('-')}`}
      label={`${pair.headline}, repeated trades`}
      // team-tap-exempt: the whole row is one expand toggle; the pair's teams open from the Teams tab
      leading={<PairAvatars pair={pair} teams={teams} />}
      title={pair.headline}
      caption={`${pair.summary} · ${CONFIDENCE_LABEL[pair.confidence]}`}
      action={<ToneBadge label={BAND_LABEL[pair.band]} color={toneColor(pair.band)} />}
      defaultOpen
    >
      <Bullets title="Evidence" items={pair.evidence} styles={styles} icon="alert" color={toneColor(pair.band)} />
      <Bullets title="Could be innocent" items={pair.innocent_explanations} styles={styles} icon="info" color={accent} />
    </ExpandRow>
  );
}

function InactiveRow({
  leagueId,
  leagueName,
  manager,
  teams,
  accent,
  infoColor,
  styles,
}: {
  leagueId: string;
  leagueName: string;
  manager: IntegrityInactiveManager;
  teams: IntegrityTeam[];
  accent: string;
  infoColor: string;
  styles: ReturnType<typeof createStyles>;
}) {
  const avatar = manager.avatar_url ?? teams.find((t) => t.roster_id === manager.roster_id)?.avatar_url;
  return (
    <ExpandRow
      testID={`integrity-inactive-${manager.roster_id}`}
      label={`${manager.team_name}, possibly inactive`}
      // team-tap-exempt: the whole row is one expand toggle; the team sheet opens from the "Open team" link inside it
      leading={<TeamAvatar avatarId={avatar} name={manager.team_name} size={32} />}
      title={manager.team_name}
      caption={manager.owner_name || undefined}
      action={<ToneBadge label="Possibly inactive" color={accent} />}
      defaultOpen
    >
      <TeamNameLink leagueId={leagueId} leagueName={leagueName} rosterId={manager.roster_id} name={manager.team_name} ownerName={manager.owner_name} avatarId={avatar} textStyle={styles.teamLink}>
        Open team
      </TeamNameLink>
      <Bullets title="Evidence" items={manager.evidence} styles={styles} icon="clock" color={accent} />
      <Bullets title="Could be innocent" items={manager.innocent_explanations} styles={styles} icon="info" color={infoColor} />
    </ExpandRow>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.lg },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
    stack: { gap: spacing.md },
    flex: { flex: 1 },
    cardHead: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.sm },
    teamLink: { fontSize: 14, fontWeight: '800', color: colors.accent },
    teamName: { fontSize: 17, fontWeight: '800', color: colors.textPrimary },
    body: { fontSize: 15.5, color: colors.textSecondary },
    muted: { fontSize: 13.5, color: colors.textTertiary },
    link: { fontSize: 13.5, fontWeight: '700', color: colors.accent },
    bullets: { gap: spacing.xs },
    bulletsTitle: { fontSize: 12.5, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8, color: colors.textTertiary },
    cardHeadCenter: { alignItems: 'center' },
    summaryRow: { flexDirection: 'row', alignItems: 'center' },
    tileRow: { flexDirection: 'row', gap: spacing.sm },
    tile: { minWidth: 0, flexBasis: 0, flexGrow: 1 },
    progressTrack: { height: 6, width: '100%', backgroundColor: colors.border, overflow: 'hidden' },
    progressFill: { height: '100%' },
    legend: { flexDirection: 'row', gap: spacing.md },
    legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    legendDot: { width: 8, height: 8, borderRadius: 2 },
    bars: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      gap: 4,
      height: 68,
      paddingHorizontal: spacing.sm,
      paddingTop: spacing.sm,
      backgroundColor: colors.glass,
      borderRadius: 6,
    },
    barCol: { flex: 1, alignItems: 'center', gap: 2 },
    barLabel: { fontSize: 12, color: colors.textTertiary },
  });
}
