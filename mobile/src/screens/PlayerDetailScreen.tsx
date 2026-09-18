import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import WeeklyPointsChart from '../components/WeeklyPointsChart';
import {
  api,
  type PlayerAward,
  type QuickViewBio,
  type QuickViewModel,
  type QuickViewSeason,
  type QuickViewStatItem,
  type QuickViewStats,
  type WeeklyStatPoint,
} from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { resolvePlayerTier } from '../lib/playerTier';
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

function SectionHeading({ title, icon }: { title: string; icon: IoniconName }) {
  return (
    <View style={styles.sectionHeadingRow}>
      <Ionicons name={icon} size={15} color={colors.accent} style={styles.sectionHeadingIcon} />
      <Text style={styles.sectionTitle}>{title}</Text>
    </View>
  );
}

function StatCell({ label, value }: { label: string; value: string | number | null }) {
  const display = value === null || value === undefined || value === '' ? '—' : value;
  return (
    <View style={styles.statCell}>
      <Text style={styles.statCellLabel} numberOfLines={1}>
        {label}
      </Text>
      <Text style={styles.statCellValue} numberOfLines={1}>
        {display}
      </Text>
    </View>
  );
}

function StatGrid({ items }: { items: Array<{ label: string; value: string | number | null }> }) {
  return (
    <View style={styles.statGrid}>
      {items.map((item, index) => (
        <StatCell key={`${item.label}-${index}`} label={item.label} value={item.value} />
      ))}
    </View>
  );
}

function StatSection({
  title,
  icon,
  items,
}: {
  title: string;
  icon: IoniconName;
  items: QuickViewStatItem[];
}) {
  if (items.length === 0) return null;
  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <SectionHeading title={title} icon={icon} />
      <StatGrid items={items.map((item) => ({ label: item.label, value: item.value || null }))} />
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

function PercentBar({ label, percent, display }: { label: string; percent: number; display: string }) {
  return (
    <View style={styles.percentRow}>
      <View style={styles.percentLabelRow}>
        <Text style={styles.percentLabel} numberOfLines={1}>
          {label}
        </Text>
        <Text style={styles.percentValue}>{display}</Text>
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
    <View style={[styles.card, styles.cardSpaced]}>
      <SectionHeading title="Usage" icon="speedometer-outline" />
      {items.map((item, index) => {
        const percent = item.value ? parsePercent(item.value) : null;
        if (percent === null) {
          return (
            <View key={`${item.label}-${index}`} style={styles.percentFallbackRow}>
              <StatCell label={item.label} value={item.value || null} />
            </View>
          );
        }
        return <PercentBar key={`${item.label}-${index}`} label={item.label} percent={percent} display={item.value} />;
      })}
    </View>
  );
}

function TrendsSection({
  seasons,
  playerId,
}: {
  seasons: QuickViewSeason[];
  playerId: string;
}) {
  const years = Array.from(new Set(seasons.map((s) => s.season).filter((s): s is number => s != null))).sort(
    (a, b) => b - a,
  );
  const [selectedYear, setSelectedYear] = useState<number | null>(years[0] ?? null);
  const [weeks, setWeeks] = useState<WeeklyStatPoint[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedYear === null) return;
    let cancelled = false;
    setLoading(true);
    api
      .getPlayerWeeklyStats(playerId, selectedYear)
      .then((result) => {
        if (!cancelled) setWeeks(result.weeks);
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

  if (years.length === 0) {
    return <Text style={styles.notice}>No weekly trend data available for this player yet.</Text>;
  }

  return (
    <View style={styles.card}>
      <SectionHeading title="Points By Week" icon="trending-up-outline" />
      {years.length > 1 ? (
        <View style={styles.yearRow}>
          {years.map((year) => (
            <TouchableOpacity
              key={year}
              style={[styles.yearPill, selectedYear === year && styles.yearPillActive]}
              onPress={() => setSelectedYear(year)}
            >
              <Text style={[styles.yearPillText, selectedYear === year && styles.yearPillTextActive]}>{year}</Text>
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

const AWARD_TIER_COLORS: Record<string, string> = {
  gold: '#D8B85A',
  silver: '#D7DBE2',
  bronze: '#9DA4AE',
};

function AwardsSection({ awards }: { awards: PlayerAward[] }) {
  if (awards.length === 0) return null;
  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <SectionHeading title="Awards" icon="trophy-outline" />
      <View style={styles.awardsWrap}>
        {awards.map((award) => {
          const tierColor = award.tier ? AWARD_TIER_COLORS[award.tier] : colors.border;
          return (
            <View key={award.badge_id} style={[styles.awardChip, { borderLeftColor: tierColor }]}>
              <View style={[styles.awardMedal, { backgroundColor: `${tierColor}26` }]}>
                <Ionicons name="medal" size={18} color={tierColor} />
              </View>
              <View style={styles.awardChipTextGroup}>
                <Text style={[styles.awardChipLabel, { color: tierColor }]}>{award.short_label}</Text>
                {award.season ? <Text style={styles.awardChipSeason}>{award.season}</Text> : null}
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
          <Text style={[styles.tabPillText, active === tab.key && styles.tabPillTextActive]}>{tab.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

function SeasonCard({
  season,
  expanded,
  onToggle,
}: {
  season: QuickViewSeason;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <TouchableOpacity style={styles.seasonCardHeader} onPress={onToggle} activeOpacity={0.7}>
        <SectionHeading title={season.label} icon="calendar-outline" />
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textTertiary} />
      </TouchableOpacity>
      {expanded ? (
        season.key_stats.length > 0 ? (
          <StatGrid items={season.key_stats.map((item) => ({ label: item.label, value: item.value || null }))} />
        ) : (
          <Text style={styles.notice}>No stats recorded for this season.</Text>
        )
      ) : null}
    </View>
  );
}

// Every past season used to render fully expanded at once — with several
// years of history that's a wall of stat grids to scroll past just to
// compare two seasons. Only the most recent stays open by default; older
// ones collapse to just their header until tapped.
function CareerSection({ seasons }: { seasons: QuickViewSeason[] }) {
  const [expandedIndex, setExpandedIndex] = useState(0);
  if (seasons.length === 0) {
    return <Text style={styles.notice}>No season history available for this player yet.</Text>;
  }
  return (
    <>
      {seasons.map((season, index) => (
        <SeasonCard
          key={`${season.season ?? 'season'}-${season.season_type}-${index}`}
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

function ModelSection({ model }: { model: QuickViewModel }) {
  const trendKey = (model.workload_trend ?? '').toLowerCase();
  const trendColor = WORKLOAD_TREND_COLOR[trendKey] ?? colors.textSecondary;
  return (
    <View style={styles.card}>
      <SectionHeading title="Model Breakdown" icon="analytics-outline" />
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
          <Text style={[styles.trendText, { color: trendColor }]}>Workload trend: {model.workload_trend}</Text>
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
  const [rank, setRank] = useState({
    overall_rank: player.overall_rank,
    position_rank: player.position_rank,
    rank_unavailable_reason: player.rank_unavailable_reason,
  });

  useScreenHeaderTitle(navigation, player.name ?? 'Player');

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
        setWatching(result.targets.some((target) => target.player_id === player.player_id));
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

  const season = stats?.seasons[0];
  const tierIdentity = resolvePlayerTier(player.tier);

  return (
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <View style={styles.header}>
        <PlayerAvatar playerId={player.player_id} size={88} tier={player.tier} style={styles.heroAvatar} />
        <Text style={styles.name}>{player.name ?? 'Unknown player'}</Text>
        <View style={styles.heroMetaRow}>
          <PositionBadge position={player.position} size="md" />
          {player.team ? <Text style={styles.meta}>{player.team}</Text> : null}
        </View>
        {player.tier ? (
          <View style={[styles.tierBadge, { backgroundColor: `${tierIdentity.color}29`, borderColor: tierIdentity.color }]}>
            <Text style={[styles.tierText, { color: tierIdentity.color }]}>{tierIdentity.shortLabel}</Text>
          </View>
        ) : null}
        {watching !== null ? (
          <TouchableOpacity
            style={[styles.watchButton, watching && styles.watchButtonActive]}
            onPress={toggleWatch}
            disabled={watchBusy}
          >
            <Text style={[styles.watchButtonText, watching && styles.watchButtonTextActive]}>
              {watching ? '★ Watching' : '☆ Add to GM Targets'}
            </Text>
          </TouchableOpacity>
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
        <Text style={styles.notice}>{rank.rank_unavailable_reason}</Text>
      ) : null}

      {loading ? (
        <ActivityIndicator style={styles.loader} color={colors.accent} />
      ) : (
        <>
          <AwardsSection awards={awards} />

          {stats?.seasons.length || model ? <TabRow active={activeTab} onChange={setActiveTab} /> : null}

          {activeTab === 'stats' && season ? (
            <>
              <Text style={styles.seasonLabel}>{season.label}</Text>
              <StatSection title="Production" icon="bar-chart-outline" items={season.key_stats} />
              <StatSection title="Fantasy" icon="american-football-outline" items={season.fantasy} />
              <UsageSection items={season.usage} />
              {stats?.college_available ? (
                <StatSection title="College" icon="school-outline" items={stats.college} />
              ) : null}
            </>
          ) : null}

          {activeTab === 'trends' ? (
            <TrendsSection seasons={stats?.seasons ?? []} playerId={player.player_id} />
          ) : null}

          {activeTab === 'career' ? <CareerSection seasons={stats?.seasons ?? []} /> : null}

          {activeTab === 'model' ? (
            model ? (
              <ModelSection model={model} />
            ) : (
              <Text style={styles.notice}>No model breakdown available for this player yet.</Text>
            )
          ) : null}

          {bio ? <BioSection bio={bio} /> : null}
          {!season && !model && !stats?.college_available && !bio && awards.length === 0 ? (
            <Text style={styles.notice}>No additional stats available for this player yet.</Text>
          ) : null}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  header: { alignItems: 'center', marginBottom: spacing.xl },
  heroAvatar: { marginBottom: spacing.md },
  name: { fontSize: 22, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  heroMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
  meta: { fontSize: 14, color: colors.textSecondary },
  tierBadge: {
    marginTop: spacing.sm,
    backgroundColor: colors.badgeBackground,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  tierText: { color: colors.badgeText, fontSize: 12, fontWeight: '700' },
  watchButton: {
    marginTop: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  watchButtonActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  watchButtonText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  watchButtonTextActive: { color: '#fff' },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
  },
  cardSpaced: { marginTop: spacing.lg },
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
  trendText: { fontSize: 12, fontWeight: '600' },
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
    backgroundColor: colors.background,
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
  percentRow: { marginBottom: spacing.sm },
  percentFallbackRow: { marginBottom: spacing.sm },
  percentLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  percentLabel: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  percentValue: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
  percentTrack: {
    height: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.background,
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
