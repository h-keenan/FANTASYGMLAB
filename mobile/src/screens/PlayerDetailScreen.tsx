import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import PlayerAvatar from '../components/PlayerAvatar';
import { api, type PlayerAward, type QuickViewBio, type QuickViewStatItem, type QuickViewStats } from '../lib/api';
import { resolvePlayerTier } from '../lib/playerTier';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

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

export default function PlayerDetailScreen({ route, navigation }: Props) {
  const { player, leagueId } = route.params;
  const [stats, setStats] = useState<QuickViewStats | null>(null);
  const [bio, setBio] = useState<QuickViewBio | null>(null);
  const [awards, setAwards] = useState<PlayerAward[]>([]);
  const [loading, setLoading] = useState(true);
  const [watching, setWatching] = useState<boolean | null>(null);
  const [watchBusy, setWatchBusy] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: player.name ?? 'Player' });
  }, [navigation, player.name]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getPlayerQuickView(player.player_id)
      .then((result) => {
        if (cancelled) return;
        setStats(result.stats);
        setBio(result.bio);
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
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <PlayerAvatar playerId={player.player_id} size={88} tier={player.tier} style={styles.heroAvatar} />
        <Text style={styles.name}>{player.name ?? 'Unknown player'}</Text>
        <Text style={styles.meta}>
          {[player.position, player.team].filter(Boolean).join(' · ')}
        </Text>
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
            { label: 'Overall rank', value: player.overall_rank },
            { label: 'Position rank', value: player.position_rank },
            { label: 'Age', value: player.age },
            { label: 'Status', value: player.status },
            { label: 'Injury status', value: player.injury_status ?? 'Healthy' },
          ]}
        />
      </View>

      {player.rank_unavailable_reason ? (
        <Text style={styles.notice}>{player.rank_unavailable_reason}</Text>
      ) : null}

      {loading ? (
        <ActivityIndicator style={styles.loader} color={colors.accent} />
      ) : (
        <>
          <AwardsSection awards={awards} />
          {season ? (
            <>
              <Text style={styles.seasonLabel}>{season.label}</Text>
              <StatSection title="Production" icon="bar-chart-outline" items={season.key_stats} />
              <StatSection title="Fantasy" icon="american-football-outline" items={season.fantasy} />
              <StatSection title="Usage" icon="speedometer-outline" items={season.usage} />
            </>
          ) : null}
          {stats?.college_available ? (
            <StatSection title="College" icon="school-outline" items={stats.college} />
          ) : null}
          {bio ? <BioSection bio={bio} /> : null}
          {!season && !stats?.college_available && !bio && awards.length === 0 ? (
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
  meta: { fontSize: 14, color: colors.textSecondary, marginTop: spacing.xs },
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
  notice: {
    marginTop: spacing.md,
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  loader: { marginTop: spacing.xl },
});
