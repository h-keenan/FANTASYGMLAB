import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import { api, type MeResponse } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../lib/supabase';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

interface SavedLeague {
  id: string;
  league_id: string;
  league_name: string;
  is_default: boolean;
}

export default function HomeScreen({ navigation }: Props) {
  const { session, signOut } = useAuth();
  const [me, setMe] = useState<MeResponse['user'] | null>(null);
  const [leagues, setLeagues] = useState<SavedLeague[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [meError, setMeError] = useState<string | null>(null);
  const [leaguesError, setLeaguesError] = useState<string | null>(null);

  // Independent requests: the backend API and Supabase are separate
  // services, so one failing (e.g. the API isn't reachable) shouldn't also
  // blank out the other or get misread as "you have no saved leagues".
  const load = useCallback(async () => {
    setMeError(null);
    setLeaguesError(null);

    const [meResult, leaguesResult] = await Promise.allSettled([
      api.getMe(),
      supabase
        .from('saved_leagues')
        .select('id, league_id, league_name, is_default')
        .order('is_default', { ascending: false }),
    ]);

    if (meResult.status === 'fulfilled') {
      setMe(meResult.value.user);
    } else {
      setMeError(
        meResult.reason instanceof Error
          ? meResult.reason.message
          : 'Could not reach the FantasyGM Lab API.',
      );
    }

    if (leaguesResult.status === 'fulfilled') {
      if (leaguesResult.value.error) {
        setLeaguesError(leaguesResult.value.error.message);
      } else {
        setLeagues((leaguesResult.value.data as SavedLeague[]) ?? []);
      }
    } else {
      setLeaguesError('Could not load your saved leagues.');
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.email}>{session?.user.email}</Text>
          {me ? (
            <TouchableOpacity
              disabled={me.entitlement === 'premium'}
              onPress={() => navigation.navigate('Paywall')}
              style={[
                styles.entitlementPill,
                me.entitlement === 'premium' && styles.entitlementPillPremium,
              ]}
            >
              <Text
                style={[
                  styles.entitlementText,
                  me.entitlement === 'premium' && styles.entitlementTextPremium,
                ]}
              >
                {me.entitlement === 'premium' ? 'Premium' : 'Free — Upgrade'}
              </Text>
            </TouchableOpacity>
          ) : null}
        </View>
        <TouchableOpacity onPress={() => void signOut()} hitSlop={8}>
          <Text style={styles.signOut}>Sign out</Text>
        </TouchableOpacity>
      </View>

      {meError ? (
        <Text style={styles.error}>Couldn't load your account: {meError}</Text>
      ) : null}
      {leaguesError ? (
        <Text style={styles.error}>Couldn't load your leagues: {leaguesError}</Text>
      ) : null}

      <Text style={styles.sectionTitle}>Your leagues</Text>
      <FlatList
        data={leagues ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={
          <Text style={styles.empty}>
            {leaguesError
              ? 'Could not check your saved leagues — pull to retry.'
              : "No leagues saved yet. Add one from the web app first — this app reads the same saved leagues as your FantasyGM Lab account."}
          </Text>
        }
        renderItem={({ item }) => (
          <AnimatedCard
            style={styles.leagueCard}
            onPress={() =>
              navigation.navigate('LeagueDetail', {
                leagueId: item.league_id,
                leagueName: item.league_name || 'League',
              })
            }
          >
            <View style={styles.leagueRow}>
              <Text style={styles.leagueName} numberOfLines={1}>
                {item.league_name || item.league_id}
              </Text>
              {item.is_default ? (
                <View style={styles.defaultBadge}>
                  <Text style={styles.defaultBadgeText}>Default</Text>
                </View>
              ) : null}
            </View>
          </AnimatedCard>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.lg,
  },
  email: { fontSize: 17, fontWeight: '600', color: colors.textPrimary, marginBottom: spacing.xs },
  entitlementPill: {
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
    backgroundColor: colors.border,
  },
  entitlementPillPremium: {
    backgroundColor: '#FEF3C7',
  },
  entitlementText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  entitlementTextPremium: { color: '#92400E' },
  signOut: { color: colors.danger, fontSize: 14, fontWeight: '500' },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm,
  },
  listContent: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    gap: spacing.sm,
  },
  leagueCard: {
    padding: spacing.lg,
  },
  leagueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  leagueName: { flex: 1, fontSize: 16, fontWeight: '500', color: colors.textPrimary, marginRight: spacing.sm },
  defaultBadge: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  defaultBadgeText: { fontSize: 11, fontWeight: '700', color: '#fff' },
  empty: {
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.md,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm,
  },
});
