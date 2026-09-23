import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  Modal,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnalyticsSection from '../components/AnalyticsSection';
import AwardsStrip from '../components/AwardsStrip';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import MetricCard from '../components/MetricCard';
import PlayerHero from '../components/PlayerHero';
import PlayerSnapshotCard, { type SnapshotItem } from '../components/PlayerSnapshotCard';
import PlayerTags, { type PlayerTagSpec } from '../components/PlayerTags';
import SegmentedTabBar from '../components/SegmentedTabBar';
import WeeklyPointsChart from '../components/WeeklyPointsChart';
import { percentileColor, percentileLabel, percentileTrendIcon } from '../lib/percentile';
import {
  api,
  type CareerSeason,
  type LineupPlayer,
  type NewsItem,
  type PlayerAward,
  type QuickViewBio,
  type QuickViewModel,
  type QuickViewStatItem,
  type QuickViewStats,
  type ScheduleWeek,
  type UsageTrend,
  type WeeklyStatPoint,
} from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { contrastTextColor, resolvePlayerTier } from '../lib/playerTier';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type DetailTab = 'stats' | 'trends' | 'schedule' | 'career' | 'model';
const TABS: Array<{ key: DetailTab; label: string }> = [
  { key: 'stats', label: 'Stats' },
  { key: 'trends', label: 'Trends' },
  { key: 'schedule', label: 'Schedule' },
  { key: 'career', label: 'Career' },
  { key: 'model', label: 'Model' },
];

type Props = NativeStackScreenProps<RootStackParamList, 'PlayerDetail'>;

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

// Same event taxonomy NewsScreen badges with — tone here maps to "good /
// bad / neutral" per coridian_'s ask rather than News's own icon set:
// speculative always reads as "pending" regardless of event type, since an
// unconfirmed injury or trade rumor isn't yet a confirmed positive/negative.
function newsImpactColor(colors: ThemeColors): Record<string, string> {
  return {
    'injury/status': colors.danger,
    transaction: colors.textSecondary,
    'role/depth chart': colors.success,
    'off-field/drama': colors.danger,
  };
}

const NEWS_IMPACT_LABEL: Record<string, string> = {
  'injury/status': 'Injury News',
  transaction: 'Transaction',
  'role/depth chart': 'Role Change',
  'off-field/drama': 'Off-Field News',
};

function NewsImpactBadge({ items, onPress }: { items: NewsItem[]; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (items.length === 0) return null;
  const top = items[0];
  const pending = top.speculative;
  const color = pending ? colors.premium : newsImpactColor(colors)[top.event_type ?? ''] ?? colors.textSecondary;
  const label = pending ? 'Pending' : NEWS_IMPACT_LABEL[top.event_type ?? ''] ?? 'In The News';
  return (
    <TouchableOpacity
      style={[styles.newsImpactBadge, { borderColor: color, backgroundColor: `${color}1F` }]}
      onPress={onPress}
    >
      <Ionicons name="newspaper-outline" size={13} color={color} />
      <AppText style={[styles.newsImpactText, { color }]}>{label}</AppText>
      <Ionicons name="chevron-forward" size={13} color={color} />
    </TouchableOpacity>
  );
}

function NewsImpactModal({
  visible,
  items,
  onClose,
}: {
  visible: boolean;
  items: NewsItem[];
  onClose: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <View style={styles.modalHeaderRow}>
            <AppText style={styles.modalTitle}>In The News</AppText>
            <TouchableOpacity onPress={onClose} hitSlop={8}>
              <Ionicons name="close" size={22} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.modalScroll}>
            {items.map((item, index) => (
              <TouchableOpacity
                key={item.link ?? `${item.title}-${index}`}
                style={styles.modalArticle}
                onPress={() => {
                  if (item.link) void Linking.openURL(item.link);
                }}
              >
                {item.speculative ? <AppText style={styles.modalSpeculative}>Unconfirmed / speculative</AppText> : null}
                <AppText style={styles.modalArticleTitle}>{item.title}</AppText>
                {item.summary ? <AppText style={styles.modalArticleSummary}>{item.summary}</AppText> : null}
                {item.source ? <AppText style={styles.modalArticleSource}>Source: {item.source}</AppText> : null}
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

function SectionHeading({ title, icon }: { title: string; icon: IoniconName }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.sectionHeadingRow}>
      <Ionicons name={icon} size={15} color={colors.accent} style={styles.sectionHeadingIcon} />
      <AppText style={styles.sectionTitle}>{title}</AppText>
    </View>
  );
}

/** Real start/sit read, not a new computation — the same
 * suggest_optimal_lineup pass My Team and Matchup already run against the
 * caller's own roster, just looked up for this one player. Omitted
 * entirely (not a guess) when the player isn't found on the caller's
 * roster at all — a free agent or an opponent's player has no "should you
 * start them" answer on this account. */
interface RosterRecommendation {
  isStarter: boolean;
  player: LineupPlayer;
}

function findRosterRecommendation(
  starters: LineupPlayer[],
  bench: LineupPlayer[],
  playerId: string,
): RosterRecommendation | null {
  const starter = starters.find((p) => p.player_id === playerId);
  if (starter) return { isStarter: true, player: starter };
  const benched = bench.find((p) => p.player_id === playerId);
  if (benched) return { isStarter: false, player: benched };
  return null;
}

function rosterRecommendationDetail(rec: RosterRecommendation): string {
  if (rec.isStarter) {
    const slot = rec.player.slot ? ` at ${rec.player.slot}` : '';
    return `Suggested starter${slot} on your roster${
      rec.player.opportunity_label ? ` — ${rec.player.opportunity_label}` : ''
    }`;
  }
  return `Not in your suggested starting lineup this week${
    rec.player.injury_label ? ` — ${rec.player.injury_label}` : ''
  }`;
}

// Derived from modules.rankings.AGE_CURVE_CONTROL_POINTS server-side — the
// same age curve already discounting this player's dynasty value, not a
// separately invented projection. See QuickViewStats.prime_window.
function primeWindowLabel(window: QuickViewStats['prime_window']): string | null {
  if (!window) return null;
  const range = `${Math.round(window.start_age)}–${Math.round(window.end_age)}`;
  if (window.status === 'before') return `Enters Prime · ${range}`;
  if (window.status === 'after') return `Past Prime · ${range}`;
  return `In Prime · ${range}`;
}

function primeWindowColor(status: 'before' | 'in' | 'after', colors: ThemeColors): string {
  if (status === 'in') return colors.successBright;
  if (status === 'before') return colors.accentSoft;
  return colors.textTertiary;
}

function StatCell({
  label,
  value,
  percentile,
}: {
  label: string;
  value: string | number | null;
  percentile?: number | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const display = value === null || value === undefined || value === '' ? '—' : value;
  const pctl = percentileLabel(percentile);
  return (
    <View style={styles.statCell}>
      <AppText style={styles.statCellLabel} numberOfLines={1}>
        {label}
      </AppText>
      <View style={styles.statCellValueRow}>
        <AppText style={styles.statCellValue} numberOfLines={1}>
          {display}
        </AppText>
        {pctl ? (
          <View style={styles.statCellPercentileRow}>
            <Ionicons name={percentileTrendIcon(percentile)!} size={11} color={percentileColor(percentile, colors)} />
            <AppText style={[styles.statCellPercentile, { color: percentileColor(percentile, colors) }]} numberOfLines={1}>
              {pctl}
            </AppText>
          </View>
        ) : null}
      </View>
    </View>
  );
}

function StatGrid({
  items,
}: {
  items: Array<{ label: string; value: string | number | null; percentile?: number | null }>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.statGrid}>
      {items.map((item, index) => (
        <StatCell
          key={`${item.label}-${index}`}
          label={item.label}
          value={item.value}
          percentile={item.percentile}
        />
      ))}
    </View>
  );
}

/** "72%" -> 72; anything else (blank, non-percent stats) -> null, so the
 * caller falls back to a plain StatCell instead of drawing an empty bar. */
function parsePercent(value: string): number | null {
  const match = /^(\d+(?:\.\d+)?)%$/.exec(value.trim());
  if (!match) return null;
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : null;
}

function PercentBar({
  label,
  percent,
  display,
  percentile,
}: {
  label: string;
  percent: number;
  display: string;
  percentile?: number | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const pctl = percentileLabel(percentile);
  return (
    <View style={styles.percentRow}>
      <View style={styles.percentLabelRow}>
        <AppText style={styles.percentLabel} numberOfLines={1}>
          {label}
        </AppText>
        <View style={styles.percentValueGroup}>
          <AppText style={styles.percentValue}>{display}</AppText>
          {pctl ? (
            <View style={styles.statCellPercentileRow}>
              <Ionicons name={percentileTrendIcon(percentile)!} size={11} color={percentileColor(percentile, colors)} />
              <AppText style={[styles.statCellPercentile, { color: percentileColor(percentile, colors) }]}>{pctl}</AppText>
            </View>
          ) : null}
        </View>
      </View>
      <View style={styles.percentTrack}>
        <View style={[styles.percentFill, { width: `${percent}%` }]} />
      </View>
    </View>
  );
}

/** Usage stats (Snap %, Route %, Target Share, Carry Share, Opportunity)
 * are all shares — a plain number is harder to size up at a glance than a
 * bar, so this renders each as one instead of falling through to the
 * generic StatGrid the other sections use. Renders bare rows only — the
 * caller (AnalyticsSection) supplies the card chrome and "Usage" heading. */
function UsageRows({ items }: { items: QuickViewStatItem[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <>
      {items.map((item, index) => {
        const percent = item.value ? parsePercent(item.value) : null;
        if (percent === null) {
          return (
            <View key={`${item.label}-${index}`} style={styles.percentFallbackRow}>
              <StatCell label={item.label} value={item.value || null} percentile={item.percentile} />
            </View>
          );
        }
        return (
          <PercentBar
            key={`${item.label}-${index}`}
            label={item.label}
            percent={percent}
            display={item.value}
            percentile={item.percentile}
          />
        );
      })}
    </>
  );
}

// Receiving-specific labels split out of `season.key_stats` — the backend's
// _key_stats already orders these together per position (see
// modules/player_quick_view.py's _key_stats `order` map), this just groups
// them under their own "Receiving" card instead of "Production" per the
// concept sheet's split, e.g. RB: Production = Games/Rush Att/Rush Yards/
// Rush TDs/Targets, Receiving = Receptions/Rec Yards/Rec TDs. Pure relabeling
// of already-computed items — no new metric is invented.
const RECEIVING_LABELS = new Set(['Receptions', 'Rec Yards', 'Rec TDs']);

function splitProductionStats(items: QuickViewStatItem[]): {
  production: QuickViewStatItem[];
  receiving: QuickViewStatItem[];
} {
  const production: QuickViewStatItem[] = [];
  const receiving: QuickViewStatItem[] = [];
  for (const item of items) {
    (RECEIVING_LABELS.has(item.label) ? receiving : production).push(item);
  }
  return { production, receiving };
}

// Mirrors services/mobile_api_service.py's MAX_WEEKLY_STATS_SEASONS_BACK —
// the weekly-stats endpoint already serves up to 3 prior seasons on
// request, but a single-season player (e.g. week 1 of a rookie year, or
// just the current season in view) previously had no year list to pick
// from at all: the picker was built from quick-view's `seasons`, which is
// always a ONE-element tuple (the current season only — see
// player_quick_view.py's `seasons=(season_view,)`), so it could never
// produce more than one year and the picker silently never rendered. Build
// the year list from the season the weekly-stats endpoint itself reports
// as current instead, so a lightly-played current season still lets you
// page back to last year or the year before.
const WEEKLY_STATS_SEASONS_BACK = 3;

/** "Rookie" or "N season(s)" — see modules/player_quick_view.py's
 * build_executive_snapshot (years_exp=0 -> "Rookie", else "{n} season(s)").
 * Returns how many seasons before the current one actually happened, so
 * the year picker below doesn't offer tabs for years before the player
 * was in the league (coridian_: "it shouldn't show other years if he's a
 * rookie this year"). Null (parse failure/no bio yet) falls back to the
 * full 3-year window rather than guessing wrong in the other direction. */
function priorSeasonsFromExperience(yearsInLeague: string | null): number | null {
  if (!yearsInLeague) return null;
  if (yearsInLeague === 'Rookie') return 0;
  const match = /^(\d+)\s+season/.exec(yearsInLeague);
  return match ? Number(match[1]) : null;
}

function TrendsSection({ playerId, yearsInLeague }: { playerId: string; yearsInLeague: string | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Set once from the first response and never touched again — the anchor
  // for the year picker's window, independent of whichever year the user
  // has since tapped over to.
  const [defaultYear, setDefaultYear] = useState<number | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [weeks, setWeeks] = useState<WeeklyStatPoint[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getPlayerWeeklyStats(playerId, selectedYear ?? undefined)
      .then((result) => {
        if (cancelled) return;
        setWeeks(result.weeks);
        setSelectedYear((current) => current ?? result.season);
        setDefaultYear((current) => current ?? result.season);
      })
      .catch(() => {
        if (!cancelled) setWeeks([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, selectedYear]);

  if (!loading && defaultYear === null) {
    return <AppText style={styles.notice}>No weekly trend data available for this player yet.</AppText>;
  }

  const priorSeasons = priorSeasonsFromExperience(yearsInLeague);
  const seasonCount =
    priorSeasons === null ? WEEKLY_STATS_SEASONS_BACK : Math.min(WEEKLY_STATS_SEASONS_BACK, priorSeasons + 1);
  const yearOptions = defaultYear === null
    ? []
    : Array.from({ length: seasonCount }, (_, index) => defaultYear - index);

  return (
    <View style={styles.card}>
      <SectionHeading title="Points By Week" icon="trending-up-outline" />
      {yearOptions.length > 1 ? (
        <View style={styles.yearRow}>
          {yearOptions.map((year) => (
            <TouchableOpacity
              key={year}
              style={[styles.yearPill, selectedYear === year && styles.yearPillActive]}
              onPress={() => setSelectedYear(year)}
            >
              <AppText style={[styles.yearPillText, selectedYear === year && styles.yearPillTextActive]}>{year}</AppText>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}
      {loading || weeks === null ? (
        <ActivityIndicator style={styles.loader} color={colors.accent} />
      ) : (
        <WeeklyPointsChart weeks={weeks} />
      )}
    </View>
  );
}

function BioSection({ bio }: { bio: QuickViewBio }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const rows: Array<[string, string]> = [
    ['Experience', bio.years_in_league],
    ['Draft capital', bio.draft_capital],
    ['College', bio.college],
    ['Height', bio.height],
    ['Weight', bio.weight],
    ['Bye week', bio.bye_week],
    ['Contract', bio.contract_status],
  ].filter(([, value]) => Boolean(value)) as Array<[string, string]>;

  if (rows.length === 0) return null;

  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <SectionHeading title="Bio" icon="person-outline" />
      <StatGrid items={rows.map(([label, value]) => ({ label, value }))} />
    </View>
  );
}

function CareerSeasonCard({
  season,
  expanded,
  onToggle,
}: {
  season: CareerSeason;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const label = `${season.season} ${season.current_season ? 'Regular Season (in progress)' : 'Regular Season'}`;
  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <TouchableOpacity style={styles.seasonCardHeader} onPress={onToggle} activeOpacity={0.7}>
        <SectionHeading title={label} icon="calendar-outline" />
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textTertiary} />
      </TouchableOpacity>
      {expanded ? (
        season.key_stats.length > 0 ? (
          <StatGrid items={season.key_stats.map((item) => ({ label: item.label, value: item.value || null }))} />
        ) : (
          <AppText style={styles.notice}>No stats recorded for this season.</AppText>
        )
      ) : null}
    </View>
  );
}

// Player Quick View's own `stats.seasons` is a single-current-season tuple
// by design (see player_quick_view.py's docstring) — the same limitation
// TrendsSection above already worked around for the points-by-week chart.
// This fetches the real multi-season resume from its own endpoint instead
// of reusing quick-view's stats, so a veteran's prior years actually show
// up here rather than only ever rendering the current season.
//
// Every past season used to render fully expanded at once — with several
// years of history that's a wall of stat grids to scroll past just to
// compare two seasons. Only the most recent stays open by default; older
// ones collapse to just their header until tapped.
function CareerSection({ playerId }: { playerId: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [seasons, setSeasons] = useState<CareerSeason[] | null>(null);
  const [expandedIndex, setExpandedIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getPlayerCareer(playerId)
      .then((result) => {
        if (!cancelled) setSeasons(result.seasons);
      })
      .catch(() => {
        if (!cancelled) setSeasons([]);
      });
    return () => {
      cancelled = true;
    };
  }, [playerId]);

  if (seasons === null) {
    return <ActivityIndicator style={styles.loader} color={colors.accent} />;
  }
  if (seasons.length === 0) {
    return <AppText style={styles.notice}>No season history available for this player yet.</AppText>;
  }
  return (
    <>
      {seasons.map((season, index) => (
        <CareerSeasonCard
          key={season.season}
          season={season}
          expanded={expandedIndex === index}
          onToggle={() => setExpandedIndex(expandedIndex === index ? -1 : index)}
        />
      ))}
    </>
  );
}

/** One real game row: week, opponent, home/away, and whatever the market
 * has actually published for it — a final score once played, otherwise
 * the real spread/total (never estimated) or a plain "not posted yet"
 * note when the market hasn't priced that week yet. */
/** Tough defense = bad matchup for this player's offense (danger/red);
 * weak defense = good matchup (success/green); average or unranked (not
 * enough completed games yet) stays the normal text color. Never used for
 * anything but this display — see nfl_schedule.team_defense_strength's own
 * docstring for why this is real points-allowed data, not a per-player
 * grade. */
function defenseTierColor(tier: ScheduleWeek['opponent_defense_tier'], colors: ThemeColors): string {
  if (tier === 'tough') return colors.danger;
  if (tier === 'weak') return colors.success;
  return colors.textPrimary;
}

function ScheduleRow({ week }: { week: ScheduleWeek }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const spreadText =
    week.spread_line != null
      ? week.spread_line < 0
        ? `Favored by ${Math.abs(week.spread_line).toFixed(1)}`
        : week.spread_line > 0
          ? `Underdog by ${week.spread_line.toFixed(1)}`
          : 'Even'
      : null;
  return (
    <View style={styles.scheduleRow}>
      <View style={styles.scheduleWeekCol}>
        <AppText style={styles.scheduleWeekLabel}>WK {week.week}</AppText>
      </View>
      <View style={styles.scheduleOpponentCol}>
        {week.bye ? (
          <AppText style={styles.scheduleBye}>BYE</AppText>
        ) : (
        <AppText
          style={[styles.scheduleOpponent, { color: defenseTierColor(week.opponent_defense_tier, colors) }]}
          numberOfLines={1}
        >
          {week.is_home ? 'vs' : '@'} {week.opponent}
        </AppText>
        )}
        {week.bye ? null : week.played ? (
          <AppText style={styles.scheduleDetail}>
            Final: {week.team_score != null ? Math.round(week.team_score) : '—'}-
            {week.opponent_score != null ? Math.round(week.opponent_score) : '—'}
          </AppText>
        ) : spreadText || week.total_line != null ? (
          <AppText style={styles.scheduleDetail}>
            {spreadText}
            {spreadText && week.total_line != null ? ' · ' : ''}
            {week.total_line != null ? `O/U ${week.total_line}` : ''}
          </AppText>
        ) : (
          <AppText style={styles.scheduleDetailMuted}>Line not posted yet</AppText>
        )}
      </View>
    </View>
  );
}

function ScheduleSection({ playerId }: { playerId: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [weeks, setWeeks] = useState<ScheduleWeek[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getPlayerSchedule(playerId)
      .then((result) => {
        if (!cancelled) setWeeks(result.weeks);
      })
      .catch(() => {
        if (!cancelled) setWeeks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [playerId]);

  if (weeks === null) {
    return <ActivityIndicator style={styles.loader} color={colors.accent} />;
  }
  if (weeks.length === 0) {
    return <AppText style={styles.notice}>No schedule available for this player's team yet.</AppText>;
  }
  return (
    <View style={styles.card}>
      <AppText style={styles.scheduleDisclaimer}>
        Real opponent, market lines, and opponent defense strength (from actual points allowed) —
        never used to adjust this player's value or rankings.
      </AppText>
      {weeks.map((week) => (
        <ScheduleRow key={week.week} week={week} />
      ))}
    </View>
  );
}

/** Same opportunity_label real string Waivers/My Team already show (never
 * a new value computed here) — colored by the same good/caution/bad read
 * those screens imply through context, so it reads as an "insight chip"
 * at a glance instead of plain gray label text. */
function opportunityChipColor(label: string | null | undefined, colors: ThemeColors): string {
  const normalized = (label ?? '').toLowerCase();
  if (!normalized) return colors.textSecondary;
  if (normalized.includes('elite') || normalized.includes('strong')) return colors.success;
  if (normalized.includes('risk') || normalized.includes('committee') || normalized.includes('backup')) {
    return colors.premium;
  }
  if (normalized.includes('out') || normalized.includes('buried')) return colors.danger;
  return colors.textSecondary;
}

function workloadTrendColor(colors: ThemeColors): Record<string, string> {
  return {
    rising: colors.success,
    climbing: colors.success,
    increasing: colors.success,
    falling: colors.danger,
    declining: colors.danger,
    decreasing: colors.danger,
  };
}

/**
 * The weekly-usage recency read, as a tinted chip. Purely a renderer: the
 * server has already decided this read is strong enough to state (see
 * UsageTrend / modules/rankings.py's recency_trend_display), so anything
 * non-null here gets shown, and nothing is re-thresholded client-side.
 */
function UsageTrendChip({ trend }: { trend: UsageTrend }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const rising = trend.direction === 'up';
  const tint = rising ? colors.success : colors.danger;
  const tintMuted = rising ? colors.successMuted : colors.dangerMuted;
  return (
    <View style={[styles.usageTrendChip, { backgroundColor: tintMuted, borderColor: tint }]}>
      <Ionicons name={rising ? 'arrow-up' : 'arrow-down'} size={12} color={tint} />
      <AppText style={[styles.usageTrendValue, { color: tint }]}>
        {trend.trend_pct > 0 ? '+' : ''}
        {trend.trend_pct}%
      </AppText>
      <AppText style={styles.usageTrendLabel} numberOfLines={1}>
        {trend.label.toLowerCase()} · {trend.confidence_label}
      </AppText>
    </View>
  );
}

/** Two real signals already computed server-side — model.workload_trend
 * (role direction) and model.usage_trend (weekly-recency read, with its own
 * confidence label) — restyled as the concept sheet's icon/title/subtitle
 * insight chips instead of the plain text line this data used to render as
 * on the Model tab only. Never invents a third chip to fill the row. */
function InsightChipsRow({ model }: { model: QuickViewModel }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const trendKey = (model.workload_trend ?? '').toLowerCase();
  const trendColor = workloadTrendColor(colors)[trendKey] ?? colors.textSecondary;
  const trendUp = trendKey === 'rising' || trendKey === 'climbing' || trendKey === 'increasing';
  const chips: Array<{ icon: IoniconName; color: string; title: string; detail: string }> = [];
  if (model.workload_trend) {
    chips.push({
      icon: trendUp ? 'trending-up' : 'trending-down',
      color: trendColor,
      title: `Role trending ${trendUp ? 'up' : 'down'}`,
      detail: model.workload_trend,
    });
  }
  if (model.usage_trend) {
    const rising = model.usage_trend.direction === 'up';
    chips.push({
      icon: rising ? 'flame' : 'alert-circle-outline',
      color: rising ? colors.success : colors.danger,
      title: model.usage_trend.label,
      detail: model.usage_trend.detail,
    });
  }
  if (chips.length === 0) return null;
  return (
    <View style={styles.insightChipsRow}>
      {chips.map((chip, index) => (
        <View key={index} style={styles.insightChip}>
          <IconCircle name={chip.icon} color={chip.color} size={30} iconSize={15} />
          <View style={styles.insightChipTextGroup}>
            <AppText style={styles.insightChipTitle} numberOfLines={1}>
              {chip.title}
            </AppText>
            <AppText style={styles.insightChipDetail} numberOfLines={2}>
              {chip.detail}
            </AppText>
          </View>
        </View>
      ))}
    </View>
  );
}

function ModelSection({ model }: { model: QuickViewModel }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const trendKey = (model.workload_trend ?? '').toLowerCase();
  const trendColor = workloadTrendColor(colors)[trendKey] ?? colors.textSecondary;
  return (
    <View style={styles.card}>
      <SectionHeading title="Model Breakdown" icon="analytics-outline" />
      {model.decision_fit_narrative ? (
        <AppText style={styles.decisionFitNarrative}>{model.decision_fit_narrative}</AppText>
      ) : null}
      <StatGrid
        items={[
          { label: 'Market', value: model.market_score != null ? Math.round(model.market_score) : null },
          { label: 'Opportunity', value: model.opportunity_score != null ? Math.round(model.opportunity_score) : null },
          { label: 'Scarcity', value: model.scarcity_score != null ? Math.round(model.scarcity_score) : null },
          { label: 'Role', value: model.role_score != null ? Math.round(model.role_score) : null },
          { label: model.age_score_label, value: model.age_score != null ? Math.round(model.age_score) : null },
          {
            label: 'Confidence',
            value: model.opportunity_confidence != null ? `${Math.round(model.opportunity_confidence)}%` : null,
          },
        ]}
      />
      {model.workload_trend ? (
        <View style={styles.trendRow}>
          <Ionicons name="trending-up-outline" size={14} color={trendColor} />
          <AppText style={[styles.trendText, { color: trendColor }]}>Workload trend: {model.workload_trend}</AppText>
        </View>
      ) : null}
      {model.usage_trend ? (
        <View style={styles.usageTrendBlock}>
          <UsageTrendChip trend={model.usage_trend} />
          <AppText style={styles.usageTrendDetail}>{model.usage_trend.detail}</AppText>
        </View>
      ) : null}
    </View>
  );
}

/** Coarse good/neutral/bad read for the Snapshot card's Status cell —
 * purely a color hint over the same `player.status` string every list
 * screen already shows verbatim; never a second status computation. */
function statusTone(status: string | null | undefined): SnapshotItem['tone'] {
  const normalized = (status ?? '').toLowerCase();
  if (!normalized) return 'neutral';
  if (normalized.includes('active')) return 'success';
  if (normalized.includes('injured') || normalized.includes('out') || normalized.includes('ir') || normalized.includes('suspend')) {
    return 'danger';
  }
  return 'neutral';
}

/** Same read for the Injury Status cell — a null/absent value already means
 * "Healthy" everywhere else in this app (see the old Snapshot's own
 * `?? 'Healthy'` fallback), so that fallback keeps its green tone here too. */
function injuryTone(injuryStatus: string | null | undefined): SnapshotItem['tone'] {
  if (!injuryStatus) return 'success';
  const normalized = injuryStatus.toLowerCase();
  if (normalized.includes('healthy')) return 'success';
  if (normalized.includes('out') || normalized.includes('ir') || normalized.includes('doubtful')) return 'danger';
  return 'neutral';
}

export default function PlayerDetailScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { player, leagueId, leagueName } = route.params;
  const [stats, setStats] = useState<QuickViewStats | null>(null);
  const [model, setModel] = useState<QuickViewModel | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>('stats');
  const [bio, setBio] = useState<QuickViewBio | null>(null);
  const [awards, setAwards] = useState<PlayerAward[]>([]);
  const [loading, setLoading] = useState(true);
  const [watching, setWatching] = useState<boolean | null>(null);
  const [watchBusy, setWatchBusy] = useState(false);
  const [untouchable, setUntouchable] = useState(false);
  const [untouchableBusy, setUntouchableBusy] = useState(false);
  const [rosterRec, setRosterRec] = useState<RosterRecommendation | null>(null);
  const [rank, setRank] = useState({
    overall_rank: player.overall_rank,
    position_rank: player.position_rank,
    rank_unavailable_reason: player.rank_unavailable_reason,
  });
  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  const [newsModalOpen, setNewsModalOpen] = useState(false);

  useScreenHeaderTitle(navigation, player.name ?? 'Player');

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  useEffect(() => {
    let cancelled = false;
    api
      .getPlayerNews(player.player_id)
      .then((result) => {
        if (!cancelled) setNewsItems(result.items);
      })
      .catch(() => {
        // Best-effort enrichment — no badge shows if this fails.
      });
    return () => {
      cancelled = true;
    };
  }, [player.player_id]);

  useEffect(() => {
    // Several callers (Waivers, MyTeam, Trade Hub) only ever have a lean
    // player shape with no rank fields to pass in route params, so this
    // screen always fetches the real league-adjusted rank itself instead of
    // trusting whatever (if anything) the tapped-from screen supplied.
    let cancelled = false;
    api
      .getPlayerRankInLeague(leagueId, player.player_id)
      .then((result) => {
        if (cancelled) return;
        if (!result.player) {
          // A bare "—" with no explanation read as a broken/glitched load
          // (coridian_: "occasional glitch where it doesn't load the
          // information") when this is really just a player outside the
          // current rankings pool (recently signed, practice squad, etc.)
          // — say so instead of leaving the dash unexplained.
          setRank({
            overall_rank: null,
            position_rank: null,
            rank_unavailable_reason: "Not enough current data to rank this player yet.",
          });
          return;
        }
        setRank({
          overall_rank: result.player.overall_rank,
          position_rank: result.player.position_rank,
          rank_unavailable_reason: result.player.rank_unavailable_reason,
        });
      })
      .catch(() => {
        // A real network/request failure — keep whatever the route params
        // already had (often nothing) rather than asserting a specific
        // reason we don't actually know; this is an enrichment fetch, not
        // a blocking one.
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, player.player_id]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getPlayerQuickView(player.player_id)
      .then((result) => {
        if (cancelled) return;
        setStats(result.stats);
        setBio(result.bio);
        setModel(result.model);
      })
      .catch(() => {
        // Quick View is a nice-to-have enrichment — the core rank card above
        // already rendered, so a failed fetch just leaves those sections out.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [player.player_id]);

  useEffect(() => {
    let cancelled = false;
    api
      .getPlayerAwards(player.player_id)
      .then((result) => {
        if (!cancelled) setAwards(result.awards);
      })
      .catch(() => {
        // Awards are an enrichment — a failed fetch just omits the section.
      });
    return () => {
      cancelled = true;
    };
  }, [player.player_id]);

  useEffect(() => {
    let cancelled = false;
    api
      .getLeagueMyTeam(leagueId)
      .then((result) => {
        if (cancelled || result.reason) return;
        setRosterRec(findRosterRecommendation(result.starters, result.bench, player.player_id));
      })
      .catch(() => {
        // Best-effort enrichment — omitting the card is the correct
        // fallback, never a guessed status.
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, player.player_id]);

  useEffect(() => {
    let cancelled = false;
    api
      .getGmTargets(leagueId)
      .then((result) => {
        if (cancelled) return;
        const target = result.targets.find((t) => t.player_id === player.player_id);
        setWatching(Boolean(target));
        setUntouchable(Boolean(target?.untouchable));
      })
      .catch(() => {
        if (!cancelled) setWatching(null);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, player.player_id]);

  const toggleWatch = async () => {
    if (watching === null || watchBusy) return;
    setWatchBusy(true);
    try {
      if (watching) {
        await api.removeGmTarget(leagueId, player.player_id);
        setWatching(false);
        setUntouchable(false);
      } else {
        const result = await api.addGmTarget(leagueId, player.player_id, 'player_detail');
        if (result.ok) {
          setWatching(true);
        } else if (result.reason === 'at_cap') {
          Alert.alert(
            'GM Targets is full',
            `You've hit the cap for this league (${result.cap ?? 'limit reached'}). Remove a target before adding another.`,
          );
        } else {
          Alert.alert('Could not update GM Targets', 'Please try again in a moment.');
        }
      }
    } catch {
      Alert.alert('Could not update GM Targets', 'Please try again in a moment.');
    } finally {
      setWatchBusy(false);
    }
  };

  const toggleUntouchable = async () => {
    if (untouchableBusy) return;
    const next = !untouchable;
    setUntouchableBusy(true);
    setUntouchable(next);
    try {
      const result = await api.setGmTargetUntouchable(leagueId, player.player_id, next);
      if (!result.ok) {
        setUntouchable(!next);
        Alert.alert('Could not update untouchable', 'Please try again in a moment.');
      }
    } catch {
      setUntouchable(!next);
      Alert.alert('Could not update untouchable', 'Please try again in a moment.');
    } finally {
      setUntouchableBusy(false);
    }
  };

  const season = stats?.seasons[0];
  const tierIdentity = resolvePlayerTier(player.tier, isDark);
  // The 2K-style headline: one 0-99 read on the same value_score the
  // Snapshot card below already shows, percentiled inside the player's
  // position by the same backend machinery as the per-stat percentiles on
  // the Stats tab. Null (too thin a pool to rank against) renders nothing —
  // the hero just falls back to the plain portrait it had before.
  const rawOverall = stats?.overall_rating;
  const overallRating =
    rawOverall === null || rawOverall === undefined || !Number.isFinite(rawOverall)
      ? null
      : rawOverall;

  const tags: PlayerTagSpec[] = [];
  if (player.tier) {
    tags.push({
      key: 'tier',
      label: tierIdentity.shortLabel,
      color: tierIdentity.color,
      variant: 'solid',
      contrastText: contrastTextColor(tierIdentity.color),
    });
  }
  if (stats?.prime_window) {
    tags.push({
      key: 'prime',
      label: primeWindowLabel(stats.prime_window) ?? '',
      color: primeWindowColor(stats.prime_window.status, colors),
      variant: 'outline',
    });
  }
  if (player.opportunity_label) {
    tags.push({
      key: 'opportunity',
      label: player.opportunity_label,
      color: opportunityChipColor(player.opportunity_label, colors),
      variant: 'outline',
    });
  }

  const snapshotItems: SnapshotItem[] = [
    {
      key: 'overall_rank',
      label: 'Overall Rank',
      value: rank.overall_rank,
      descriptor: rank.overall_rank != null ? 'of all players' : null,
    },
    {
      key: 'position_rank',
      label: 'Position Rank',
      value: rank.position_rank,
      descriptor: rank.position_rank != null && player.position ? `of ${player.position}s` : null,
    },
    { key: 'age', label: 'Age', value: player.age },
    { key: 'status', label: 'Status', value: player.status, tone: statusTone(player.status) },
    {
      key: 'injury',
      label: 'Injury Status',
      value: player.injury_status ?? 'Healthy',
      tone: injuryTone(player.injury_status),
    },
  ];

  const heroActions = (
    <>
      <PlayerTags tags={tags} />
      {rosterRec ? (
        <View
          style={[
            styles.rosterRecCard,
            { borderColor: rosterRec.isStarter ? colors.success : colors.textTertiary },
          ]}
        >
          <View
            style={[
              styles.rosterRecBadge,
              { backgroundColor: rosterRec.isStarter ? colors.success : colors.backgroundElevated },
            ]}
          >
            <AppText
              style={[
                styles.rosterRecBadgeText,
                { color: rosterRec.isStarter ? colors.background : colors.textSecondary },
              ]}
            >
              {rosterRec.isStarter ? 'STARTER' : 'BENCH'}
            </AppText>
          </View>
          <View style={styles.rosterRecTextGroup}>
            <AppText style={styles.rosterRecTitle}>Roster Recommendation</AppText>
            <AppText style={styles.rosterRecDetail}>{rosterRecommendationDetail(rosterRec)}</AppText>
          </View>
        </View>
      ) : null}
      <NewsImpactBadge items={newsItems} onPress={() => setNewsModalOpen(true)} />
      {watching !== null ? (
        <View style={styles.watchRow}>
          <TouchableOpacity
            style={[styles.watchButton, watching && styles.watchButtonActive]}
            onPress={toggleWatch}
            disabled={watchBusy}
          >
            <AppText style={[styles.watchButtonText, watching && styles.watchButtonTextActive]}>
              {watching ? '★ Watching' : '☆ Add to GM Targets'}
            </AppText>
          </TouchableOpacity>
          {watching ? (
            <TouchableOpacity
              style={[styles.untouchableButton, untouchable && styles.untouchableButtonActive]}
              onPress={toggleUntouchable}
              disabled={untouchableBusy}
              accessibilityLabel={untouchable ? 'Remove untouchable flag' : 'Mark untouchable'}
            >
              <Ionicons
                name={untouchable ? 'lock-closed' : 'lock-open-outline'}
                size={16}
                color={untouchable ? colors.background : colors.textSecondary}
              />
            </TouchableOpacity>
          ) : null}
          <TouchableOpacity
            style={styles.compareButton}
            onPress={() => navigation.navigate('PlayerCompare', { player, leagueId, leagueName })}
          >
            <Ionicons name="swap-vertical-outline" size={14} color={colors.accent} />
            <AppText style={styles.compareButtonText}>Compare</AppText>
          </TouchableOpacity>
        </View>
      ) : null}
    </>
  );

  // Built as an array (rather than a JSX fragment) so the segmented tab
  // bar's position can be computed dynamically and passed to the
  // ScrollView's `stickyHeaderIndices` — the brief asks for the subnav to
  // "remain easily accessible as the user scrolls" via a sticky treatment,
  // and the index has to reflect whatever actually rendered above it (the
  // rank-unavailable notice and the loading spinner are both conditional).
  const content: React.ReactNode[] = [];
  content.push(
    <PlayerHero
      key="hero"
      playerId={player.player_id}
      tier={player.tier}
      name={player.name ?? 'Unknown player'}
      position={player.position}
      team={player.team}
      overallRating={overallRating}
      ringColor={overallRating !== null ? percentileColor(overallRating, colors) : colors.accent}
      glowColor={tierIdentity.color}
    >
      {heroActions}
    </PlayerHero>,
  );
  content.push(<PlayerSnapshotCard key="snapshot" valueScore={player.score != null ? Math.round(player.score) : null} items={snapshotItems} />);
  if (rank.rank_unavailable_reason) {
    content.push(
      <AppText key="rank-note" style={styles.notice}>
        {rank.rank_unavailable_reason}
      </AppText>,
    );
  }

  let tabBarIndex: number | null = null;

  if (loading) {
    content.push(<ActivityIndicator key="loading" style={styles.loader} color={colors.accent} />);
  } else {
    content.push(<AwardsStrip key="awards" awards={awards} />);

    const showTabs = Boolean(stats?.seasons.length || model);
    if (showTabs) {
      tabBarIndex = content.length;
      content.push(
        <View key="tabbar" style={styles.tabBarWrap}>
          <SegmentedTabBar options={TABS} active={activeTab} onChange={setActiveTab} />
        </View>,
      );
    }

    if (activeTab === 'stats' && season) {
      const { production, receiving } = splitProductionStats(season.key_stats);
      content.push(
        <View key="stats-tab">
          <AppText style={styles.seasonLabel}>{season.label}</AppText>
          {season.fantasy.length > 0 ? (
            <AnalyticsSection title="Fantasy Scoring" icon="american-football-outline">
              <View style={styles.metricGrid}>
                {season.fantasy.map((item, index) => (
                  <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} />
                ))}
              </View>
            </AnalyticsSection>
          ) : null}
          {production.length > 0 ? (
            <AnalyticsSection title="Production" icon="bar-chart-outline">
              <View style={styles.metricGrid}>
                {production.map((item, index) => (
                  <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} />
                ))}
              </View>
            </AnalyticsSection>
          ) : null}
          {receiving.length > 0 ? (
            <AnalyticsSection title="Receiving" icon="locate-outline">
              <View style={styles.metricGrid}>
                {receiving.map((item, index) => (
                  <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} />
                ))}
              </View>
            </AnalyticsSection>
          ) : null}
          {season.usage.length > 0 ? (
            <AnalyticsSection title="Usage" icon="speedometer-outline">
              <UsageRows items={season.usage} />
            </AnalyticsSection>
          ) : null}
          {season.efficiency.length > 0 ? (
            <AnalyticsSection title="Efficiency" icon="calculator-outline">
              <View style={styles.metricGrid}>
                {season.efficiency.map((item, index) => (
                  <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} />
                ))}
              </View>
            </AnalyticsSection>
          ) : null}
          {stats?.college_available && stats.college.length > 0 ? (
            <AnalyticsSection title="College" icon="school-outline">
              <View style={styles.metricGrid}>
                {stats.college.map((item, index) => (
                  <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} />
                ))}
              </View>
            </AnalyticsSection>
          ) : null}
          {model ? <InsightChipsRow model={model} /> : null}
        </View>,
      );
    }

    if (activeTab === 'trends') {
      content.push(
        <TrendsSection key="trends-tab" playerId={player.player_id} yearsInLeague={bio?.years_in_league ?? null} />,
      );
    }

    if (activeTab === 'schedule') {
      content.push(<ScheduleSection key="schedule-tab" playerId={player.player_id} />);
    }

    if (activeTab === 'career') {
      content.push(<CareerSection key="career-tab" playerId={player.player_id} />);
    }

    if (activeTab === 'model') {
      content.push(
        model ? (
          <ModelSection key="model-tab" model={model} />
        ) : (
          <AppText key="model-tab" style={styles.notice}>
            No model breakdown available for this player yet.
          </AppText>
        ),
      );
    }

    if (bio) {
      content.push(<BioSection key="bio" bio={bio} />);
    }
    if (!season && !model && !stats?.college_available && !bio && awards.length === 0) {
      content.push(
        <AppText key="empty-notice" style={styles.notice}>
          No additional stats available for this player yet.
        </AppText>,
      );
    }
  }

  return (
    <>
    <View style={styles.root}>
    <GridBackground />
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
      stickyHeaderIndices={tabBarIndex !== null ? [tabBarIndex] : undefined}
    >
      {content}
    </ScrollView>
    </View>
    <NewsImpactModal visible={newsModalOpen} items={newsItems} onClose={() => setNewsModalOpen(false)} />
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1 },
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  watchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
  watchButton: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  watchButtonActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  watchButtonText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  watchButtonTextActive: { color: '#fff' },
  untouchableButton: {
    width: 34,
    height: 34,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  untouchableButtonActive: { backgroundColor: colors.premium, borderColor: colors.premium },
  compareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  compareButtonText: { fontSize: 13, fontWeight: '600', color: colors.accent },
  rosterRecCard: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'stretch',
    gap: spacing.sm,
    marginTop: spacing.sm,
    padding: spacing.sm,
    borderRadius: radii.md,
    borderWidth: 1,
    backgroundColor: colors.surface,
  },
  rosterRecBadge: { paddingHorizontal: spacing.sm, paddingVertical: 4, borderRadius: radii.pill },
  rosterRecBadgeText: { fontSize: 11, fontWeight: '800', letterSpacing: 0.4 },
  rosterRecTextGroup: { flex: 1 },
  rosterRecTitle: { fontSize: 12, fontWeight: '700', color: colors.textPrimary },
  rosterRecDetail: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  newsImpactBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  newsImpactText: { fontSize: 12, fontWeight: '700' },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  modalCard: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    maxHeight: '75%',
    padding: spacing.lg,
  },
  modalHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  modalTitle: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  modalScroll: { flexGrow: 0 },
  modalArticle: {
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  modalArticleTitle: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, marginBottom: 4 },
  modalArticleSummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginBottom: 4 },
  modalArticleSource: { fontSize: 11, color: colors.textTertiary },
  modalSpeculative: {
    fontSize: 11,
    color: colors.premium,
    fontWeight: '700',
    marginBottom: 4,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
  },
  cardSpaced: { marginTop: spacing.lg },
  // Sticky segmented tab bar: an opaque fill (matching the page background)
  // so scrolled-past content doesn't show through once this pins to the
  // top, per the brief's "remain easily accessible as the user scrolls".
  tabBarWrap: {
    backgroundColor: colors.background,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  insightChipsRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  insightChip: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    padding: spacing.sm,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    backgroundColor: colors.surface,
  },
  insightChipTextGroup: { flex: 1 },
  insightChipTitle: { fontSize: 12, fontWeight: '700', color: colors.textPrimary },
  insightChipDetail: { fontSize: 10, color: colors.textSecondary, marginTop: 1, lineHeight: 13 },
  trendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  decisionFitNarrative: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  trendText: { fontSize: 12, fontWeight: '600' },
  usageTrendBlock: { marginTop: spacing.sm, gap: spacing.xs },
  usageTrendChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm,
    borderWidth: 1,
  },
  usageTrendValue: { fontSize: 12, fontWeight: '700' },
  usageTrendLabel: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  usageTrendDetail: { fontSize: 11, color: colors.textTertiary },
  seasonLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: spacing.xl,
    marginBottom: -spacing.sm,
    textTransform: 'uppercase',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  sectionHeadingRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.sm },
  sectionHeadingIcon: { marginRight: spacing.xs },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  statCell: {
    minWidth: '46%',
    flexGrow: 1,
    // Borderless cell inside a `surface` card — it has to carry its own
    // separation, so it steps up the ramp instead of down (`background`
    // here was only 1.09 against the card, i.e. no visible cell at all).
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  statCellLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
    marginBottom: 2,
  },
  statCellValue: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
  // Suffix, not a second stat: it sits on the value's baseline and shrinks
  // first, so the density pass that folded this tab into one card holds.
  statCellValueRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.xs },
  statCellPercentileRow: { flexDirection: 'row', alignItems: 'center', gap: 2, flexShrink: 1 },
  statCellPercentile: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.accentSoft,
    letterSpacing: 0.2,
    flexShrink: 1,
  },
  percentRow: { marginBottom: spacing.sm },
  percentFallbackRow: { marginBottom: spacing.sm },
  percentLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  percentLabel: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  percentValueGroup: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.xs },
  percentValue: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
  percentTrack: {
    height: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.backgroundElevated,
    overflow: 'hidden',
  },
  percentFill: {
    height: '100%',
    borderRadius: radii.pill,
    backgroundColor: colors.accent,
  },
  seasonCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  yearRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.md },
  yearPill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    backgroundColor: colors.surfaceSolid,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  yearPillActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  yearPillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  yearPillTextActive: { color: '#fff' },
  notice: {
    marginTop: spacing.md,
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  loader: { marginTop: spacing.xl },
  scheduleDisclaimer: {
    fontSize: 11,
    color: colors.textTertiary,
    lineHeight: 15,
    marginBottom: spacing.sm,
  },
  scheduleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  scheduleWeekCol: { width: 52 },
  scheduleWeekLabel: { fontSize: 11, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  scheduleOpponentCol: { flex: 1 },
  scheduleOpponent: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  scheduleBye: { fontSize: 14, fontWeight: '700', color: colors.danger, letterSpacing: 0.4 },
  scheduleDetail: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  scheduleDetailMuted: { fontSize: 12, color: colors.textTertiary, marginTop: 1, fontStyle: 'italic' },
  });
}
