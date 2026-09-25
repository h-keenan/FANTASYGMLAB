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
import SectionHeading from '../components/SectionHeading';
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
  // "Pending" reads as an unresolved/awaiting-confirmation state (matches the
  // concept sheet's action-row pill for this exact case) — a clock icon says
  // that more clearly than the newspaper glyph confirmed news items keep.
  const icon: IoniconName = pending ? 'time-outline' : 'newspaper-outline';
  return (
    <TouchableOpacity
      style={[styles.newsImpactBadge, { borderColor: color, backgroundColor: `${color}1F` }]}
      onPress={onPress}
    >
      <Ionicons name={icon} size={13} color={color} />
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

type RosterRecTone = 'success' | 'caution' | 'danger' | 'neutral';

/** Real state read over the same LineupPlayer fields Waivers/My Team already
 * expose — never a new computation. `ruled_out` (confirmed unavailable, e.g.
 * Out/IR/PUP) is always the strongest signal regardless of starter/bench; a
 * suggested starter still carrying a weekly injury tag (Questionable, not
 * ruled out) reads as caution rather than a flat "all clear" green; a clean
 * starter is success; a healthy bench call is neutral. Replaces the old
 * two-state (green starter / gray bench) read with the four real states
 * coridian_ asked for. */
function rosterRecTone(rec: RosterRecommendation): RosterRecTone {
  if (rec.player.ruled_out) return 'danger';
  if (rec.isStarter) return rec.player.injury_label ? 'caution' : 'success';
  return 'neutral';
}

function rosterRecToneColor(tone: RosterRecTone, colors: ThemeColors): string {
  if (tone === 'success') return colors.success;
  if (tone === 'caution') return colors.premium;
  if (tone === 'danger') return colors.danger;
  return colors.textTertiary;
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

// QB's own `_key_stats` order already ends in Rush Yards/Rush TDs (see
// modules/player_quick_view.py) mixed into the same "Production" card as
// passing volume — coridian_'s brief wants QB rushing pulled out into its
// own secondary/smaller-weight treatment instead of sitting at equal visual
// weight next to Pass Att/Pass Yards/Pass TDs. Same split mechanism as
// RECEIVING_LABELS above, just keyed to the position that applies to.
const QB_RUSHING_LABELS = new Set(['Rush Yards', 'Rush TDs']);

/** Splits `season.key_stats` into the primary "Production" (QB: "Passing
 * Production") group and a secondary group — Receiving for every non-QB
 * position, QB Rushing for QB — using the label sets above. Still pure
 * relabeling/regrouping of already-computed items; no metric is invented and
 * no backend value is recomputed. */
function splitKeyStats(
  position: string,
  items: QuickViewStatItem[],
): { primary: QuickViewStatItem[]; secondary: QuickViewStatItem[] } {
  const secondaryLabels = position === 'QB' ? QB_RUSHING_LABELS : RECEIVING_LABELS;
  const primary: QuickViewStatItem[] = [];
  const secondary: QuickViewStatItem[] = [];
  for (const item of items) {
    (secondaryLabels.has(item.label) ? secondary : primary).push(item);
  }
  return { primary, secondary };
}

type StatGroupKey = 'fantasy' | 'production' | 'receiving' | 'qbRushing' | 'usage' | 'efficiency' | 'college';

const DEFAULT_STAT_GROUP_ORDER: StatGroupKey[] = ['fantasy', 'production', 'receiving', 'usage', 'efficiency', 'college'];

/**
 * Position-aware stat-group ORDER only — never which metrics exist per
 * position (that's already correctly data-driven server-side; see
 * modules/player_quick_view.py's `_key_stats`/`_fantasy_stats`/`_usage_stats`/
 * `_efficiency_stats`). coridian_'s brief: for QB, decision importance runs
 * Fantasy Output -> Passing Production -> (QB Rushing, secondary weight) ->
 * Usage -> Efficiency -> Role Trend -> Bio, with Role Trend/Bio rendered
 * outside this array (see PlayerDetailScreen's InsightChipsRow/Bio
 * placement, unchanged). One shared `AnalyticsSection`-based architecture
 * consults this table — never a per-position screen/component copy. Add a
 * position's own array here to reorder its groups; any position missing from
 * this table falls back to DEFAULT_STAT_GROUP_ORDER unchanged.
 */
const STAT_GROUP_ORDER: Partial<Record<string, StatGroupKey[]>> = {
  QB: ['fantasy', 'production', 'qbRushing', 'usage', 'efficiency', 'college'],
};

function statGroupOrderForPosition(position: string): StatGroupKey[] {
  return STAT_GROUP_ORDER[position] ?? DEFAULT_STAT_GROUP_ORDER;
}

/**
 * Fidelity fix vs. both concept sheets: neither ever wraps a 3-4 metric
 * analytics group into a 2x2 grid — RB's Fantasy Scoring and Efficiency each
 * render 4 cards in a single row, QB's Production renders 3 — whereas
 * MetricCard's own default `minWidth: '46%'` (unchanged here, still used by
 * every other caller — Dashboard, My Team, Team Roster, Player Compare)
 * always wraps a group of 3+ into multiple rows. This only overrides sizing
 * per-instance via the `style` prop MetricCard already documents for exactly
 * this purpose, so no shared-component default changes. Groups of 1-2 keep
 * the original two-up sizing; 5+ (none currently exist) falls back to it too
 * rather than squeezing five cards into an unreadable single row.
 */
function metricGroupCardStyle(count: number): { minWidth: number; flexBasis: `${number}%` } {
  if (count === 3) return { minWidth: 88, flexBasis: '31%' };
  if (count === 4) return { minWidth: 76, flexBasis: '23%' };
  return { minWidth: 120, flexBasis: '46%' };
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
    { key: 'age', label: 'Age', value: player.age, emphasis: 'supporting' },
    { key: 'status', label: 'Status', value: player.status, tone: statusTone(player.status), emphasis: 'supporting' },
    {
      key: 'injury',
      label: 'Injury Status',
      value: player.injury_status ?? 'Healthy',
      tone: injuryTone(player.injury_status),
      emphasis: 'supporting',
    },
  ];

  const rosterRecToneValue = rosterRec ? rosterRecTone(rosterRec) : null;
  const rosterRecColor = rosterRecToneValue ? rosterRecToneColor(rosterRecToneValue, colors) : colors.textTertiary;
  const hasWatchControls = watching !== null;
  const hasNews = newsItems.length > 0;

  // "Add to GM Targets" / untouchable-toggle / Compare / the news-status pill
  // now render as ONE row (coridian_'s concept sheet: 3 pill controls in a
  // single line, not a separate status bar above the actions) instead of the
  // old standalone NewsImpactBadge line sitting above its own watchRow.
  const heroActions = (
    <>
      <PlayerTags tags={tags} />
      {rosterRec ? (
        <View style={[styles.rosterRecCard, { borderColor: rosterRecColor }]}>
          <View
            style={[
              styles.rosterRecBadge,
              rosterRecToneValue === 'neutral'
                ? { backgroundColor: colors.backgroundElevated }
                : { backgroundColor: rosterRecColor },
            ]}
          >
            <AppText
              style={[
                styles.rosterRecBadgeText,
                rosterRecToneValue === 'neutral'
                  ? { color: colors.textSecondary }
                  : { color: contrastTextColor(rosterRecColor) },
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
      {hasWatchControls || hasNews ? (
        <View style={styles.actionRow}>
          {hasWatchControls ? (
            <>
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
            </>
          ) : null}
          <NewsImpactBadge items={newsItems} onPress={() => setNewsModalOpen(true)} />
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
      const position = (player.position ?? '').toUpperCase();
      const isQB = position === 'QB';
      const { primary: productionItems, secondary: secondaryItems } = splitKeyStats(position, season.key_stats);
      // Decided up front (not just at ordering time) so Efficiency's own
      // card sizing below can size for a half-width column when this will
      // actually apply — see the ordering step further down for why this is
      // gated to small groups only.
      const canPairUsageEfficiency = season.usage.length <= 2 && season.efficiency.length <= 2;

      // One group -> one rendered node, keyed by the same StatGroupKey the
      // position-aware order table above uses to sequence them — this is the
      // "consult a config, don't hardcode one fixed order" architecture the
      // brief asks for (item 17), not a per-position screen/component.
      const groupNodes: Partial<Record<StatGroupKey, React.ReactNode>> = {};

      if (season.fantasy.length > 0) {
        const cardStyle = metricGroupCardStyle(season.fantasy.length);
        groupNodes.fantasy = (
          <AnalyticsSection key="fantasy" title="Fantasy Output" icon="american-football-outline">
            <View style={styles.metricGrid}>
              {season.fantasy.map((item, index) => (
                <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} style={cardStyle} />
              ))}
            </View>
          </AnalyticsSection>
        );
      }

      if (productionItems.length > 0) {
        const cardStyle = metricGroupCardStyle(productionItems.length);
        groupNodes.production = (
          <AnalyticsSection key="production" title={isQB ? 'Passing Production' : 'Production'} icon="bar-chart-outline">
            <View style={styles.metricGrid}>
              {productionItems.map((item, index) => (
                <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} style={cardStyle} />
              ))}
            </View>
          </AnalyticsSection>
        );
      }

      if (secondaryItems.length > 0) {
        if (isQB) {
          // Secondary/smaller weight vs. the MetricCard+PercentileBar tiles
          // above — reuses StatGrid, the same lighter-weight pattern Bio/
          // Model/Career already use, rather than inventing a new component.
          groupNodes.qbRushing = (
            <AnalyticsSection key="qb-rushing" title="QB Rushing" icon="walk-outline">
              <StatGrid
                items={secondaryItems.map((item) => ({ label: item.label, value: item.value || null, percentile: item.percentile }))}
              />
            </AnalyticsSection>
          );
        } else {
          const cardStyle = metricGroupCardStyle(secondaryItems.length);
          groupNodes.receiving = (
            <AnalyticsSection key="receiving" title="Receiving" icon="locate-outline">
              <View style={styles.metricGrid}>
                {secondaryItems.map((item, index) => (
                  <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} style={cardStyle} />
                ))}
              </View>
            </AnalyticsSection>
          );
        }
      }

      if (season.usage.length > 0) {
        groupNodes.usage = (
          <AnalyticsSection key="usage" title="Usage" icon="speedometer-outline">
            <UsageRows items={season.usage} />
          </AnalyticsSection>
        );
      }

      if (season.efficiency.length > 0) {
        // Halved-column sizing when this will render next to Usage (see
        // canPairUsageEfficiency above) — the normal row-fill sizing assumes
        // a full-width section and would force a 2-item group to wrap
        // vertically inside a half-width card instead of sitting side by
        // side the way the concept sheet shows it.
        const cardStyle = canPairUsageEfficiency
          ? { minWidth: 64, flexBasis: '46%' as const }
          : metricGroupCardStyle(season.efficiency.length);
        groupNodes.efficiency = (
          <AnalyticsSection key="efficiency" title="Efficiency" icon="calculator-outline">
            <View style={styles.metricGrid}>
              {season.efficiency.map((item, index) => (
                <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} style={cardStyle} />
              ))}
            </View>
          </AnalyticsSection>
        );
      }

      if (stats?.college_available && stats.college.length > 0) {
        const cardStyle = metricGroupCardStyle(stats.college.length);
        groupNodes.college = (
          <AnalyticsSection key="college" title="College" icon="school-outline">
            <View style={styles.metricGrid}>
              {stats.college.map((item, index) => (
                <MetricCard key={`${item.label}-${index}`} label={item.label} value={item.value || null} percentile={item.percentile} style={cardStyle} />
              ))}
            </View>
          </AnalyticsSection>
        );
      }

      // Usage and Efficiency render side-by-side in one row, not stacked
      // full-width — matching the QB concept sheet (Usage's Snap % module
      // sits next to Efficiency's tiles at the same height) and reusing the
      // exact paired-column pattern already established below for
      // Awards+Bio (`awardsBioRow`/`awardsBioCol`) instead of inventing a
      // second one. Gated (canPairUsageEfficiency, above) to when both groups
      // are small (<=2 items each) — the RB concept sheet shows no Usage
      // section at all, so there's no visual evidence a 4-item Efficiency
      // group (RB's real shape) should ever be squeezed into a half-width
      // column; large groups keep the original full-width stacked layout the
      // density fix above already covers.
      const orderKeys = statGroupOrderForPosition(position);
      const orderedGroups: React.ReactNode[] = [];
      for (let i = 0; i < orderKeys.length; i += 1) {
        const key = orderKeys[i];
        if (
          key === 'usage' &&
          orderKeys[i + 1] === 'efficiency' &&
          groupNodes.usage &&
          groupNodes.efficiency &&
          canPairUsageEfficiency
        ) {
          orderedGroups.push(
            <View key="usage-efficiency-row" style={styles.pairedRow}>
              <View style={styles.pairedCol}>{groupNodes.usage}</View>
              <View style={styles.pairedCol}>{groupNodes.efficiency}</View>
            </View>,
          );
          i += 1;
          continue;
        }
        if (groupNodes[key]) orderedGroups.push(groupNodes[key]);
      }

      content.push(
        <View key="stats-tab">
          <AppText style={styles.seasonLabel}>{season.label}</AppText>
          {orderedGroups}
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

    // Awards + Bio paired at the bottom (concept sheet's 2-column row)
    // instead of Awards sitting alone above the tabs and Bio sitting alone
    // below them — both are tab-agnostic "always visible" cards either way,
    // so this only changes where they sit, not when they show.
    if (awards.length > 0 || bio) {
      content.push(
        <View key="awards-bio-row" style={styles.awardsBioRow}>
          {awards.length > 0 ? (
            <View style={styles.awardsBioCol}>
              <AwardsStrip awards={awards} />
            </View>
          ) : null}
          {bio ? (
            <View style={styles.awardsBioCol}>
              <BioSection bio={bio} />
            </View>
          ) : null}
        </View>,
      );
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
      // headerTransparent (RootNavigator) floats the native header above
      // this screen instead of reserving layout space for it, so the
      // ScrollView's own frame has to be pushed down by `useHeaderHeight()`
      // here — on the *container* `style`, not just the scrollable content's
      // top padding. That distinction is the fix: `stickyHeaderIndices`
      // pins its child to the top of the ScrollView's own frame, not to the
      // top of its (padded) content. With the old code the offset lived only
      // in `contentContainerStyle`'s `paddingTop`, so the frame itself still
      // started at y=0 under the header — once the tab bar stuck, it stuck
      // at the literal top of the screen, behind/under the transparent
      // header (status-bar and title collision) instead of just below it.
      style={[styles.container, { marginTop: headerHeight }]}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}
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
  actionRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md },
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
  // Awards + Bio paired side-by-side per the concept sheet's bottom row —
  // each column is `flex: 1` so a lone section (no awards, or no bio) still
  // fills the full row, and `minWidth: '46%'` lets the pair wrap to a
  // full-width stack on a narrow phone instead of squeezing unreadably.
  awardsBioRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  awardsBioCol: { flex: 1, minWidth: '46%' },
  // Usage+Efficiency side-by-side row — same paired-column shape as
  // awardsBioRow/awardsBioCol above, kept as its own tokens since the two
  // pairings sit in different parts of the page and may need to diverge.
  pairedRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.sm },
  pairedCol: { flex: 1, minWidth: '46%' },
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
