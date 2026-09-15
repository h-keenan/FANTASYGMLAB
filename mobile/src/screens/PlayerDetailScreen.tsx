import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import PlayerAvatar from '../components/PlayerAvatar';
import { api, type QuickViewBio, type QuickViewStatItem, type QuickViewStats } from '../lib/api';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'PlayerDetail'>;

function Stat({ label, value }: { label: string; value: string | number | null }) {
  return (
    <View style={styles.statRow}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value ?? '—'}</Text>
    </View>
  );
}

function StatItemRow({ item }: { item: QuickViewStatItem }) {
  return (
    <View style={styles.statRow}>
      <Text style={styles.statLabel}>{item.label}</Text>
      <Text style={styles.statValue}>{item.value || '—'}</Text>
    </View>
  );
}

function StatSection({ title, items }: { title: string; items: QuickViewStatItem[] }) {
  if (items.length === 0) return null;
  return (
    <View style={[styles.card, styles.cardSpaced]}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {items.map((item, index) => (
        <StatItemRow key={`${item.label}-${index}`} item={item} />
      ))}
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
      <Text style={styles.sectionTitle}>Bio</Text>
      {rows.map(([label, value]) => (
        <Stat key={label} label={label} value={value} />
      ))}
    </View>
  );
}

export default function PlayerDetailScreen({ route, navigation }: Props) {
  const { player, leagueId } = route.params;
  const [stats, setStats] = useState<QuickViewStats | null>(null);
  const [bio, setBio] = useState<QuickViewBio | null>(null);
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

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <PlayerAvatar playerId={player.player_id} size={88} style={styles.heroAvatar} />
        <Text style={styles.name}>{player.name ?? 'Unknown player'}</Text>
        <Text style={styles.meta}>
          {[player.position, player.team].filter(Boolean).join(' · ')}
        </Text>
        {player.tier ? (
          <View style={styles.tierBadge}>
            <Text style={styles.tierText}>{player.tier}</Text>
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
        <Stat label="Value score" value={player.score != null ? Math.round(player.score) : null} />
        <Stat label="Overall rank" value={player.overall_rank} />
        <Stat label="Position rank" value={player.position_rank} />
        <Stat label="Age" value={player.age} />
        <Stat label="Status" value={player.status} />
        <Stat label="Injury status" value={player.injury_status ?? 'Healthy'} />
      </View>

      {player.rank_unavailable_reason ? (
        <Text style={styles.notice}>{player.rank_unavailable_reason}</Text>
      ) : null}

      {loading ? (
        <ActivityIndicator style={styles.loader} color={colors.accent} />
      ) : (
        <>
          {season ? (
            <>
              <Text style={styles.seasonLabel}>{season.label}</Text>
              <StatSection title="Production" items={season.key_stats} />
              <StatSection title="Fantasy" items={season.fantasy} />
              <StatSection title="Usage" items={season.usage} />
            </>
          ) : null}
          {stats?.college_available ? <StatSection title="College" items={stats.college} /> : null}
          {bio ? <BioSection bio={bio} /> : null}
          {!season && !stats?.college_available && !bio ? (
            <Text style={styles.notice}>No additional stats available for this player yet.</Text>
          ) : null}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl },
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
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  statLabel: { fontSize: 14, color: colors.textSecondary },
  statValue: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  notice: {
    marginTop: spacing.md,
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  loader: { marginTop: spacing.xl },
});
