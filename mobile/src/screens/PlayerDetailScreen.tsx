import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import CircularProgressRing from '../components/CircularProgressRing';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import WeeklyPointsChart from '../components/WeeklyPointsChart';
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

/** 1 -> "1st", 22 -> "22nd", 13 -> "13th". Teens are all "th" regardless of
 * their last digit, which is the case a naive last-digit switch gets wrong. */
function ordinal(value: number): string {
  const rounded = Math.round(value);
  const lastTwo = Math.abs(rounded) % 100;
  const lastOne = Math.abs(rounded) % 10;
  if (lastTwo >= 11 && lastTwo <= 13) return `${rounded}th`;
  if (lastOne === 1) return `${rounded}st`;
  if (lastOne === 2) return `${rounded}nd`;
  if (lastOne === 3) return `${rounded}rd`;
  return `${rounded}th`;
}

/** "59 rush yards" says nothing about whether 59 is good for the position —
 * this is the peer-group answer the backend attaches to each stat. Absent
 * (null/undefined) whenever the position pool was too small to rank against,
 * in which case nothing renders rather than a made-up number. */
function percentileLabel(percentile: number | null | undefined): string | null {
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) return null;
  return `${ordinal(percentile)} pctl`;
}

/** Reads the percentile's color off a red -> gold -> green ramp so "9th" and
 * "91st" don't arrive in the same flat blue. Anchored on the existing palette
 * (danger at 0, premium at 50, successBright at 100) and interpolated
 * channel-wise rather than bucketed into three flat bands, so neighbouring
 * stats stay distinguishable instead of snapping at a cutoff. Anything
 * unrankable keeps the old accentSoft. */
function mixHex(from: string, to: string, t: number): string {
  const parse = (hex: string) => [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
  const [r1, g1, b1] = parse(from);
  const [r2, g2, b2] = parse(to);
  const channel = (a: number, b: number) =>
    Math.round(a + (b - a) * t)
      .toString(16)
      .padStart(2, '0');
  return `#${channel(r1, r2)}${channel(g1, g2)}${channel(b1, b2)}`;
}

/** Real, not fabricated: the same percentile the badge text already shows,
 * just given a direction — at/above the 50th percentile reads as a trend
 * up, below it a trend down. Never a week-over-week delta (this app has no
 * such series for most stats); the concept sheet's "trend arrows on stat
 * tiles" is satisfied here by direction-of-percentile, not invented change. */
function percentileTrendIcon(percentile: number | null | undefined): IoniconName | null {
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) return null;
  return percentile >= 50 ? 'caret-up' : 'caret-down';
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

function percentileColor(percentile: number | null | undefined, colors: ThemeColors): string {
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) {
    return colors.accentSoft;
  }
  const clamped = Math.max(0, Math.min(100, percentile));
  if (clamped <= 50) return mixHex(colors.danger, colors.premium, clamped / 50);
  return mixHex(colors.premium, colors.successBright, (clamped - 50) / 50);
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

/** `first` drops the top divider/margin — used when this is the leading
 * subsection inside a shared outer card (see the Stats tab, which groups
 * Production/Fantasy/Efficiency/Usage/College into ONE card instead of one
 * per category: five separate cards each with their own border+padding+
 * margin was the literal cause of "Usage is buried at the bottom... the UI
 * is too spaced out" — same stat density, far less card chrome between
 * categories that all describe the same season). */
function StatSection({
  title,
  icon,
  items,
  first,
}: {
  title: string;
  icon: IoniconName;
  items: QuickViewStatItem[];
  first?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (items.length === 0) return null;
  return (
    <View style={first ? undefined : styles.subSection}>
      <SectionHeading title={title} icon={icon} />
      <StatGrid
        items={items.map((item) => ({
          label: item.label,
          value: item.value || null,
          percentile: item.percentile,
        }))}
      />
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
 * generic StatGrid the other sections use. */
function UsageSection({ items }: { items: QuickViewStatItem[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (items.length === 0) return null;
  return (
    <View style={styles.subSection}>
      <SectionHeading title="Usage" icon="speedometer-outline" />
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
    </View>
  );
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

// Previous bronze (#9DA4AE) was a blue-gray, not remotely bronze-colored —
// on a small icon at dark-mode contrast, all three tiers read as "plain
// gray," which is exactly the "awards look bland" complaint. These are
// closer to actual metallic gold/silver/bronze. Untiered awards (some
// achievements have no tier — see modules/player_awards.py's tier=None
// cases) previously fell back to colors.border, nearly invisible against
// the card background; now a visible neutral accent instead.
const AWARD_TIER_COLORS: Record<string, string> = {
  gold: '#FFD700',
  silver: '#D9DFE6',
  bronze: '#CD7F32',
};

function AwardsSection({ awards }: { awards: PlayerAward[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [selectedAward, setSelectedAward] = useState<PlayerAward | null>(null);
  if (awards.length === 0) return null;
  const selectedTierColor = selectedAward
    ? (selectedAward.tier && AWARD_TIER_COLORS[selectedAward.tier]) || colors.accentSoft
    : colors.accentSoft;
  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <SectionHeading title="Awards" icon="trophy-outline" />
      <View style={styles.awardsWrap}>
        {awards.map((award) => {
          const tierColor = (award.tier && AWARD_TIER_COLORS[award.tier]) || colors.accentSoft;
          return (
            <TouchableOpacity
              key={award.badge_id}
              style={[styles.awardChip, { borderLeftColor: tierColor }]}
              onPress={() => setSelectedAward(award)}
            >
              <View style={[styles.awardMedal, { backgroundColor: `${tierColor}26` }]}>
                <Ionicons name="medal" size={18} color={tierColor} />
              </View>
              <View style={styles.awardChipTextGroup}>
                <AppText style={[styles.awardChipLabel, { color: tierColor }]}>{award.short_label}</AppText>
                {award.season ? <AppText style={styles.awardChipSeason}>{award.season}</AppText> : null}
              </View>
            </TouchableOpacity>
          );
        })}
      </View>
      <Modal visible={selectedAward !== null} transparent animationType="fade" onRequestClose={() => setSelectedAward(null)}>
        <Pressable style={styles.awardBackdrop} onPress={() => setSelectedAward(null)}>
          <Pressable style={styles.awardSheet} onPress={(event) => event.stopPropagation()}>
            {selectedAward ? (
              <>
                <View style={styles.awardSheetHeaderRow}>
                  <View style={[styles.awardMedal, { backgroundColor: `${selectedTierColor}26` }]}>
                    <Ionicons name="medal" size={22} color={selectedTierColor} />
                  </View>
                  <View style={styles.awardChipTextGroup}>
                    <AppText style={[styles.awardSheetTitle, { color: selectedTierColor }]}>{selectedAward.title}</AppText>
                    {selectedAward.season ? <AppText style={styles.awardChipSeason}>{selectedAward.season}</AppText> : null}
                  </View>
                </View>
                <AppText style={styles.awardSheetDescription}>{selectedAward.description}</AppText>
                {selectedAward.occurrence_count > 1 ? (
                  <AppText style={styles.awardSheetMeta}>
                    Earned {selectedAward.occurrence_count} times
                  </AppText>
                ) : null}
              </>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
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

function TabRow({ active, onChange }: { active: DetailTab; onChange: (tab: DetailTab) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.tabRow}>
      {TABS.map((tab) => (
        <TouchableOpacity
          key={tab.key}
          style={[styles.tabPill, active === tab.key && styles.tabPillActive]}
          onPress={() => onChange(tab.key)}
        >
          <AppText style={[styles.tabPillText, active === tab.key && styles.tabPillTextActive]}>{tab.label}</AppText>
        </TouchableOpacity>
      ))}
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
  // Snapshot grid below already shows, percentiled inside the player's
  // position by the same backend machinery as the per-stat percentiles on
  // the Stats tab. Null (too thin a pool to rank against) renders nothing —
  // the header just falls back to the centered avatar it had before.
  const rawOverall = stats?.overall_rating;
  const overallRating =
    rawOverall === null || rawOverall === undefined || !Number.isFinite(rawOverall)
      ? null
      : rawOverall;

  return (
    <>
    <View style={styles.root}>
    <GridBackground />
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
      <View style={styles.header}>
        <View style={styles.heroIdentityRow}>
          <PlayerAvatar playerId={player.player_id} size={88} tier={player.tier} />
          {overallRating !== null ? (
            <CircularProgressRing
              percent={overallRating}
              size={100}
              strokeWidth={9}
              valueLabel={String(overallRating)}
              valueFontScale={0.38}
              color={percentileColor(overallRating, colors)}
              label="Overall"
            />
          ) : null}
        </View>
        <AppText style={styles.name}>{player.name ?? 'Unknown player'}</AppText>
        <View style={styles.heroMetaRow}>
          <PositionBadge position={player.position} size="md" />
          {player.team ? <AppText style={styles.meta}>{player.team}</AppText> : null}
        </View>
        {player.tier ? (
          <View style={[styles.tierBadge, { backgroundColor: tierIdentity.color }]}>
            <AppText style={[styles.tierText, { color: contrastTextColor(tierIdentity.color) }]}>
              {tierIdentity.shortLabel}
            </AppText>
          </View>
        ) : null}
        {stats?.prime_window ? (
          <View
            style={[
              styles.primeWindowBadge,
              { borderColor: primeWindowColor(stats.prime_window.status, colors) },
            ]}
          >
            <AppText style={[styles.primeWindowText, { color: primeWindowColor(stats.prime_window.status, colors) }]}>
              {primeWindowLabel(stats.prime_window)}
            </AppText>
          </View>
        ) : null}
        {player.opportunity_label ? (
          <View style={[styles.primeWindowBadge, { borderColor: opportunityChipColor(player.opportunity_label, colors) }]}>
            <AppText style={[styles.primeWindowText, { color: opportunityChipColor(player.opportunity_label, colors) }]}>
              {player.opportunity_label}
            </AppText>
          </View>
        ) : null}
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
      </View>

      <View style={styles.card}>
        <SectionHeading title="Snapshot" icon="flash-outline" />
        <StatGrid
          items={[
            { label: 'Value score', value: player.score != null ? Math.round(player.score) : null },
            { label: 'Overall rank', value: rank.overall_rank },
            { label: 'Position rank', value: rank.position_rank },
            { label: 'Age', value: player.age },
            { label: 'Status', value: player.status },
            { label: 'Injury status', value: player.injury_status ?? 'Healthy' },
          ]}
        />
      </View>

      {rank.rank_unavailable_reason ? (
        <AppText style={styles.notice}>{rank.rank_unavailable_reason}</AppText>
      ) : null}

      {loading ? (
        <ActivityIndicator style={styles.loader} color={colors.accent} />
      ) : (
        <>
          <AwardsSection awards={awards} />

          {stats?.seasons.length || model ? <TabRow active={activeTab} onChange={setActiveTab} /> : null}

          {activeTab === 'stats' && season ? (
            <>
              <AppText style={styles.seasonLabel}>{season.label}</AppText>
              <View style={[styles.card, styles.cardSpaced]}>
                <StatSection title="Fantasy" icon="american-football-outline" items={season.fantasy} first />
                <StatSection title="Production" icon="bar-chart-outline" items={season.key_stats} />
                <UsageSection items={season.usage} />
                <StatSection title="Efficiency" icon="calculator-outline" items={season.efficiency} />
                {stats?.college_available ? (
                  <StatSection title="College" icon="school-outline" items={stats.college} />
                ) : null}
              </View>
              {model ? <InsightChipsRow model={model} /> : null}
            </>
          ) : null}

          {activeTab === 'trends' ? (
            <TrendsSection playerId={player.player_id} yearsInLeague={bio?.years_in_league ?? null} />
          ) : null}

          {activeTab === 'schedule' ? <ScheduleSection playerId={player.player_id} /> : null}

          {activeTab === 'career' ? <CareerSection playerId={player.player_id} /> : null}

          {activeTab === 'model' ? (
            model ? (
              <ModelSection model={model} />
            ) : (
              <AppText style={styles.notice}>No model breakdown available for this player yet.</AppText>
            )
          ) : null}

          {bio ? <BioSection bio={bio} /> : null}
          {!season && !model && !stats?.college_available && !bio && awards.length === 0 ? (
            <AppText style={styles.notice}>No additional stats available for this player yet.</AppText>
          ) : null}
        </>
      )}
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
  header: { alignItems: 'center', marginBottom: spacing.xl },
  heroIdentityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
    marginBottom: spacing.md,
  },
  name: { fontSize: 22, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  heroMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
  meta: { fontSize: 14, color: colors.textSecondary },
  tierBadge: {
    marginTop: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  tierText: { fontSize: 12, fontWeight: '700' },
  primeWindowBadge: {
    marginTop: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
  },
  primeWindowText: { fontSize: 12, fontWeight: '700' },
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
    padding: spacing.lg,
  },
  cardSpaced: { marginTop: spacing.lg },
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
  // A subsection inside a shared card: a hairline + modest top margin reads
  // as "next category" without the full weight of another card's
  // border+padding+margin — see StatSection's `first` prop.
  subSection: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  tabRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
  },
  tabPill: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  tabPillActive: { backgroundColor: colors.accentMuted, borderColor: colors.accent },
  tabPillText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  tabPillTextActive: { color: colors.accent },
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
  awardsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  awardChip: {
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderLeftWidth: 3,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minWidth: '46%',
    backgroundColor: colors.background,
  },
  awardMedal: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
  awardChipTextGroup: { flexShrink: 1 },
  awardChipLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.3 },
  awardChipSeason: { fontSize: 10, color: colors.textTertiary, fontWeight: '600', marginTop: 1 },
  awardBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  awardSheet: {
    backgroundColor: colors.backgroundElevated,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  awardSheetHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md },
  awardSheetTitle: { fontSize: 17, fontWeight: '800' },
  awardSheetDescription: { fontSize: 14, color: colors.textSecondary, lineHeight: 20 },
  awardSheetMeta: { fontSize: 12, color: colors.textTertiary, marginTop: spacing.sm, fontWeight: '600' },
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
