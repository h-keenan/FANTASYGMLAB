import React, { useEffect, useMemo, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import MetricCard from './MetricCard';
import MeterRow, { confidenceLevelFor } from './ConfidenceMeter';
import { ViewTabs } from './PageControlRow';
import PlayerQuickViewSheet, { Section, type SimPqvSections } from './PlayerQuickViewSheet';
import ProspectReportForm, { type ReportDraft, type ReportFlash } from './ProspectReportForm';
import { SkeletonBlock } from './Skeleton';
import ToneBadge from './ToneBadge';
import WeeklyPointsChart from './WeeklyPointsChart';
import { useThemeMode } from '../context/ThemeModeContext';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { api, type CollegeProspect } from '../lib/api';
import { planOf, type Plan } from '../lib/plan';
import { stubPlayer } from '../lib/playerQuickView';
import {
  PROSPECT_NO_STATS,
  PROSPECT_SOURCE_NAME,
  PROSPECT_SOURCE_URL,
  adpHeroTile,
  advancedTiles,
  classYearLabel,
  gameStatLine,
  handOffPlayerId,
  hometownLine,
  lineTiles,
  prospectMetaLine,
  prospectWeeklySeries,
  recruitingTiles,
  roundHeroTile,
  type ProspectProfileResponse,
  type ProspectTile,
} from '../lib/prospectProfile';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

interface LoadState {
  profile: ProspectProfileResponse | null;
  failed: boolean;
  plan: Plan;
  done: boolean;
}

function Tiles({ tiles }: { tiles: ProspectTile[] }) {
  const styles = useMemo(() => StyleSheet.create({ grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm } }), []);
  return (
    <View style={styles.grid}>
      {tiles.map((t) => (
        <MetricCard key={t.label} label={t.label} value={t.value} note={t.note || undefined} />
      ))}
    </View>
  );
}

/**
 * The college prospect detail sheet. It IS the shared player quick view (same sheet, hero header, swipeable tabs and
 * weekly chart as an NFL or Fantasy Sim player), fed a prospect's own sections through `customSections`: Overview (crowd
 * grade, round, ADP, your report, watchlist), Stats (CFBD season lines, advanced, weekly chart) and Profile (recruiting,
 * hometown). Basics are free; advanced metrics are Pro (`planOf`, withheld by the server too). Drafted + mapped hands
 * off to the normal NFL card. Web twin: web-next/src/components/ProspectSheet.tsx.
 */
export default function ProspectSheet({
  prospect,
  draft,
  flash,
  busy,
  onDraftChange,
  onSubmit,
  onRemove,
  onToggleWatchlist,
  onClose,
}: {
  prospect: CollegeProspect;
  draft: ReportDraft;
  flash: ReportFlash | null;
  busy: boolean;
  onDraftChange: (next: ReportDraft) => void;
  onSubmit: () => void;
  onRemove: () => Promise<boolean>;
  onToggleWatchlist: () => void;
  onClose: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { openPlayer } = usePlayerQuickView();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [state, setState] = useState<LoadState>({ profile: null, failed: false, plan: 'unknown', done: false });
  const [season, setSeason] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getProspectProfile(prospect.id), api.getMe().catch(() => null)])
      .then(([profile, me]) => {
        if (!cancelled) setState({ profile: profile.ok ? profile : null, failed: !profile.ok && profile.reason !== 'not_found', plan: planOf(me?.user), done: true });
      })
      .catch(() => {
        if (!cancelled) setState({ profile: null, failed: true, plan: 'unknown', done: true });
      });
    return () => {
      cancelled = true;
    };
  }, [prospect.id]);

  const { profile } = state;
  const handOffId = handOffPlayerId(prospect) ?? (profile?.prospect?.drafted ? handOffPlayerId(profile.prospect) : null);
  useEffect(() => {
    if (!handOffId) return;
    onClose();
    openPlayer(stubPlayer({ player_id: handOffId, name: prospect.name, position: prospect.position, team: profile?.prospect?.nfl_team }), { sourceLabel: 'Drafted prospect' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handOffId]);

  if (handOffId) return null;

  const aggregate = prospect.aggregate;
  const hasReport = prospect.my_report != null;
  const link = (url: string) => void Linking.openURL(url).catch(() => {});

  const source = (
    <AppText style={styles.muted} testID="prospect-source">
      Source:{' '}
      <AppText style={styles.link} onPress={() => link(profile?.source?.url ?? PROSPECT_SOURCE_URL)} accessibilityRole="link">
        {profile?.source?.name ?? PROSPECT_SOURCE_NAME}
      </AppText>
      {profile?.source?.as_of ? ` · updated ${profile.source.as_of}` : ''}
    </AppText>
  );

  const overview = (
    <View style={styles.stack} testID="prospect-overview">
      <Section title="Crowd scouting">
        {aggregate.scout_count > 0 ? (
          <MeterRow label="Signal" value={aggregate.scout_count >= 8 ? 'high' : aggregate.scout_count >= 3 ? 'medium' : 'low'} level={confidenceLevelFor(aggregate.scout_count >= 8 ? 'high' : aggregate.scout_count >= 3 ? 'medium' : 'low')} color={colors.accent} />
        ) : null}
        <AppText style={styles.strong}>
          {aggregate.avg_grade != null && aggregate.scout_count > 0
            ? `${aggregate.avg_grade.toFixed(1)} avg · ${aggregate.scout_count} ${aggregate.scout_count === 1 ? 'scout' : 'scouts'}`
            : 'Not yet scouted'}
          {aggregate.avg_round_projection != null && aggregate.scout_count > 0 ? ` · projected round ${aggregate.avg_round_projection.toFixed(1)}` : ''}
        </AppText>
        {prospect.my_report?.grade != null ? <AppText style={styles.accent}>Your grade: {prospect.my_report.grade}/5</AppText> : null}
        {state.done && profile?.adp?.source ? <AppText style={styles.muted}>Rookie ADP from {profile.adp.source.source}.</AppText> : null}
        <Button label={prospect.on_watchlist ? 'Unfollow' : 'Follow'} variant="secondary" size="sm" onPress={onToggleWatchlist} />
      </Section>
      <Section title={hasReport ? 'Your report' : `Scout ${prospect.name}`}>
        <ProspectReportForm hasReport={hasReport} draft={draft} flash={flash} busy={busy} onDraftChange={onDraftChange} onSubmit={onSubmit} onRemove={onRemove} />
      </Section>
    </View>
  );

  const stats = (() => {
    if (!state.done) return <SkeletonBlock height={160} />;
    if (state.failed) return <EmptyState icon="alert-circle-outline" title="Could not load stats" subtitle="Close the sheet and open him again." />;
    const seasons = profile?.seasons ?? [];
    const series = prospectWeeklySeries(profile?.weekly ?? null);
    if (seasons.length === 0 && !series) {
      return (
        <View style={styles.stack}>
          <EmptyState icon="stats-chart-outline" title="No college stats yet" subtitle={PROSPECT_NO_STATS} />
          {source}
        </View>
      );
    }
    const active = seasons.find((s) => String(s.season) === season) ?? seasons[0];
    const adv = advancedTiles(profile?.advanced, prospect.position);
    const games = (profile?.weekly?.games ?? []).filter((g) => g.fantasy_points != null).slice(-5).reverse();
    return (
      <View style={styles.stack} testID="prospect-stats">
        {active ? (
          <Section title={`${active.season} season${active.team ? ` · ${active.team}` : ''}`}>
            {seasons.length > 1 ? (
              <ViewTabs label="Season" options={seasons.map((s) => String(s.season))} value={String(active.season)} onChange={setSeason} />
            ) : null}
            <Tiles tiles={lineTiles(active, prospect.position)} />
            {active.fantasy_points != null ? <AppText style={styles.muted}>College fantasy points (derived): {active.fantasy_points.toFixed(1)}</AppText> : null}
          </Section>
        ) : null}
        {adv.length > 0 ? (
          <Section title="Advanced">
            <Tiles tiles={adv} />
            <AppText style={styles.muted}>PPA is predicted points added per play. Usage is his share of his team&apos;s plays.</AppText>
          </Section>
        ) : profile?.advanced_locked && state.plan === 'free' ? (
          <View style={styles.lock} testID="prospect-advanced-lock">
            <ToneBadge label="Pro" color={colors.premium} />
            <AppText style={styles.lockText}>Advanced metrics: PPA and usage</AppText>
            <Button label="See Pro" variant="premium" size="sm" onPress={() => navigation.navigate('Paywall')} />
          </View>
        ) : null}
        {series ? (
          <Section title={`Points by week · ${series.season}`}>
            <WeeklyPointsChart weeks={series.weeks} pointsLabel="college pts" />
            <AppText style={styles.muted}>Derived from {PROSPECT_SOURCE_NAME} stat lines (PPR, no fumbles).</AppText>
            {games.map((g) => (
              <AppText key={g.week} style={styles.line}>
                <AppText style={styles.strong}>{`Wk ${g.week}${g.opponent ? ` vs ${g.opponent}` : ''}`}</AppText>
                {` · ${gameStatLine(g, prospect.position)}`}
              </AppText>
            ))}
          </Section>
        ) : null}
        {source}
      </View>
    );
  })();

  const profileTab = (() => {
    if (!state.done) return <SkeletonBlock height={100} />;
    const recruiting = recruitingTiles(profile?.recruiting);
    const hometown = hometownLine(profile?.recruiting, profile?.bio?.hometown);
    const bits = [classYearLabel(profile?.bio?.class_year), prospect.school, hometown ? `From ${hometown}` : null].filter((b): b is string => Boolean(b));
    if (recruiting.length === 0 && bits.length <= 1) {
      return (
        <View style={styles.stack}>
          <EmptyState icon="person-outline" title="No profile yet" subtitle="Recruiting and hometown fill in weekly." />
          {source}
        </View>
      );
    }
    return (
      <View style={styles.stack} testID="prospect-profile">
        <Section title="Recruiting">
          {recruiting.length > 0 ? <Tiles tiles={recruiting} /> : <AppText style={styles.line}>No recruiting rank on file.</AppText>}
          {bits.length > 0 ? <AppText style={styles.line}>{bits.join(' · ')}</AppText> : null}
        </Section>
        {source}
      </View>
    );
  })();

  const sections: SimPqvSections = {
    overview,
    heroGrade: (
      <MetricCard
        label="Crowd grade"
        value={aggregate.avg_grade != null ? aggregate.avg_grade.toFixed(1) : null}
        note={aggregate.scout_count > 0 ? `${aggregate.scout_count} ${aggregate.scout_count === 1 ? 'scout' : 'scouts'}` : 'Not yet scouted'}
        centered
      />
    ),
    heroTiles: [roundHeroTile(aggregate.avg_round_projection, aggregate.scout_count), adpHeroTile(state.done ? profile?.adp : null)],
    headerMeta: { line: prospectMetaLine(prospect.draft_year, profile?.bio) || `${prospect.draft_year ?? ''} class`, logo: profile?.bio?.school_logo_url ?? null },
    stats,
    profile: profileTab,
  };

  return (
    <PlayerQuickViewSheet
      request={{ player: stubPlayer({ player_id: `prospect-${prospect.id}`, name: prospect.name, position: prospect.position, team: prospect.school }), league: null, sourceLabel: 'College prospect' }}
      onClose={onClose}
      remote={false}
      customSections={sections}
    />
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.md },
    muted: { fontSize: 12.5, color: colors.textTertiary },
    link: { fontSize: 12.5, color: colors.accent },
    strong: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    accent: { fontSize: 13.5, fontWeight: '700', color: colors.accent },
    line: { fontSize: 14, color: colors.textSecondary },
    lock: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    lockText: { flex: 1, fontSize: 14, color: colors.textSecondary, minWidth: 140 },
  });
}
