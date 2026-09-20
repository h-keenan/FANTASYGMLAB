import React, { useEffect, useState } from 'react';
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
import { Ionicons } from '@expo/vector-icons';

import CircularProgressRing from '../components/CircularProgressRing';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import WeeklyPointsChart from '../components/WeeklyPointsChart';
import {
  api,
  type CareerSeason,
  type NewsItem,
  type PlayerAward,
  type QuickViewBio,
  type QuickViewModel,
  type QuickViewStatItem,
  type QuickViewStats,
  type UsageTrend,
  type WeeklyStatPoint,
} from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { contrastTextColor, resolvePlayerTier } from '../lib/playerTier';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type DetailTab = 'stats' | 'trends' | 'career' | 'model';
const TABS: Array<{ key: DetailTab; label: string }> = [
  { key: 'stats', label: 'Stats' },
  { key: 'trends', label: 'Trends' },
  { key: 'career', label: 'Career' },
  { key: 'model', label: 'Model' },
];

type Props = NativeStackScreenProps<RootStackParamList, 'PlayerDetail'>;

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

// Same event taxonomy NewsScreen badges with — tone here maps to "good /
// bad / neutral" per coridian_'s ask rather than News's own icon set:
// speculative always reads as "pending" regardless of event type, since an
// unconfirmed injury or trade rumor isn't yet a confirmed positive/negative.
const NEWS_IMPACT_COLOR: Record<string, string> = {
  'injury/status': colors.danger,
  transaction: colors.textSecondary,
  'role/depth chart': colors.success,
  'off-field/drama': colors.danger,
};

const NEWS_IMPACT_LABEL: Record<string, string> = {
  'injury/status': 'Injury News',
  transaction: 'Transaction',
  'role/depth chart': 'Role Change',
  'off-field/drama': 'Off-Field News',
};

function NewsImpactBadge({ items, onPress }: { items: NewsItem[]; onPress: () => void }) {
  if (items.length === 0) return null;
  const top = items[0];
  const pending = top.speculative;
  const color = pending ? colors.premium : NEWS_IMPACT_COLOR[top.event_type ?? ''] ?? colors.textSecondary;
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

function percentileColor(percentile: number | null | undefined): string {
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

function primeWindowColor(status: 'before' | 'in' | 'after'): string {
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
          <AppText
            style={[styles.statCellPercentile, { color: percentileColor(percentile) }]}
            numberOfLines={1}
          >
            {pctl}
          </AppText>
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
            <AppText style={[styles.statCellPercentile, { color: percentileColor(percentile) }]}>
              {pctl}
            </AppText>
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

function TrendsSection({ playerId }: { playerId: string }) {
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

  const yearOptions = defaultYear === null
    ? []
    : Array.from({ length: WEEKLY_STATS_SEASONS_BACK }, (_, index) => defaultYear - index);

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
const AWARD_UNTIERED_COLOR = colors.accentSoft;

function AwardsSection({ awards }: { awards: PlayerAward[] }) {
  if (awards.length === 0) return null;
  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <SectionHeading title="Awards" icon="trophy-outline" />
      <View style={styles.awardsWrap}>
        {awards.map((award) => {
          const tierColor = (award.tier && AWARD_TIER_COLORS[award.tier]) || AWARD_UNTIERED_COLOR;
          return (
            <View key={award.badge_id} style={[styles.awardChip, { borderLeftColor: tierColor }]}>
              <View style={[styles.awardMedal, { backgroundColor: `${tierColor}26` }]}>
                <Ionicons name="medal" size={18} color={tierColor} />
              </View>
              <View style={styles.awardChipTextGroup}>
                <AppText style={[styles.awardChipLabel, { color: tierColor }]}>{award.short_label}</AppText>
                {award.season ? <AppText style={styles.awardChipSeason}>{award.season}</AppText> : null}
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}

function BioSection({ bio }: { bio: QuickViewBio }) {
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

const WORKLOAD_TREND_COLOR: Record<string, string> = {
  rising: colors.success,
  climbing: colors.success,
  increasing: colors.success,
  falling: colors.danger,
  declining: colors.danger,
  decreasing: colors.danger,
};

/**
 * The weekly-usage recency read, as a tinted chip. Purely a renderer: the
 * server has already decided this read is strong enough to state (see
 * UsageTrend / modules/rankings.py's recency_trend_display), so anything
 * non-null here gets shown, and nothing is re-thresholded client-side.
 */
function UsageTrendChip({ trend }: { trend: UsageTrend }) {
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

function ModelSection({ model }: { model: QuickViewModel }) {
  const trendKey = (model.workload_trend ?? '').toLowerCase();
  const trendColor = WORKLOAD_TREND_COLOR[trendKey] ?? colors.textSecondary;
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
  const { player, leagueId } = route.params;
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
  const [rank, setRank] = useState({
    overall_rank: player.overall_rank,
    position_rank: player.position_rank,
    rank_unavailable_reason: player.rank_unavailable_reason,
  });
  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  const [newsModalOpen, setNewsModalOpen] = useState(false);

  useScreenHeaderTitle(navigation, player.name ?? 'Player');

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
        if (cancelled || !result.player) return;
        setRank({
          overall_rank: result.player.overall_rank,
          position_rank: result.player.position_rank,
          rank_unavailable_reason: result.player.rank_unavailable_reason,
        });
      })
      .catch(() => {
        // Keep whatever the route params already had (often nothing) —
        // this is an enrichment, not a blocking fetch.
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
  const tierIdentity = resolvePlayerTier(player.tier);
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
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <View style={styles.header}>
        <View style={styles.heroIdentityRow}>
          <PlayerAvatar playerId={player.player_id} size={88} tier={player.tier} />
          {overallRating !== null ? (
            <CircularProgressRing
              percent={overallRating}
              size={84}
              strokeWidth={8}
              valueLabel={String(overallRating)}
              valueFontScale={0.38}
              color={percentileColor(overallRating)}
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
              { borderColor: primeWindowColor(stats.prime_window.status) },
            ]}
          >
            <AppText style={[styles.primeWindowText, { color: primeWindowColor(stats.prime_window.status) }]}>
              {primeWindowLabel(stats.prime_window)}
            </AppText>
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
            </>
          ) : null}

          {activeTab === 'trends' ? <TrendsSection playerId={player.player_id} /> : null}

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
    <NewsImpactModal visible={newsModalOpen} items={newsItems} onClose={() => setNewsModalOpen(false)} />
    </>
  );
}

const styles = StyleSheet.create({
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
    borderColor: colors.border,
  },
  watchButtonActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  watchButtonText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  watchButtonTextActive: { color: '#fff' },
  untouchableButton: {
    width: 34,
    height: 34,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  untouchableButtonActive: { backgroundColor: colors.premium, borderColor: colors.premium },
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
    borderColor: colors.border,
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
    borderColor: colors.border,
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
    borderColor: colors.border,
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
    borderColor: colors.border,
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
});
