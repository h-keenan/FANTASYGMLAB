import React, { useEffect } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

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

export default function PlayerDetailScreen({ route, navigation }: Props) {
  const { player } = route.params;

  useEffect(() => {
    navigation.setOptions({ title: player.name ?? 'Player' });
  }, [navigation, player.name]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.name}>{player.name ?? 'Unknown player'}</Text>
        <Text style={styles.meta}>
          {[player.position, player.team].filter(Boolean).join(' · ')}
        </Text>
        {player.tier ? (
          <View style={styles.tierBadge}>
            <Text style={styles.tierText}>{player.tier}</Text>
          </View>
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
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl },
  header: { alignItems: 'center', marginBottom: spacing.xl },
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
  card: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.lg,
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
});
