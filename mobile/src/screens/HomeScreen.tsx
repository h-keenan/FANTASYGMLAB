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

import { api, type MeResponse } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { supabase } from '../lib/supabase';
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
  const [leagues, setLeagues] = useState<SavedLeague[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [meResult, leaguesResult] = await Promise.all([
        api.getMe(),
        supabase
          .from('saved_leagues')
          .select('id, league_id, league_name, is_default')
          .order('is_default', { ascending: false }),
      ]);
      setMe(meResult.user);
      if (leaguesResult.error) throw new Error(leaguesResult.error.message);
      setLeagues((leaguesResult.data as SavedLeague[]) ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load your account.');
    } finally {
      setLoading(false);
    }
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
            <Text style={styles.entitlement}>
              {me.entitlement === 'premium' ? 'Premium' : 'Free'} account
            </Text>
          ) : null}
        </View>
        <TouchableOpacity onPress={() => void signOut()}>
          <Text style={styles.signOut}>Sign out</Text>
        </TouchableOpacity>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Text style={styles.sectionTitle}>Your leagues</Text>
      <FlatList
        data={leagues}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={
          <Text style={styles.empty}>
            No leagues saved yet. Add one from the web app first — this app
            reads the same saved leagues as your FantasyGM Lab account.
          </Text>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.leagueRow}
            onPress={() =>
              navigation.navigate('LeagueDetail', {
                leagueId: item.league_id,
                leagueName: item.league_name || 'League',
              })
            }
          >
            <Text style={styles.leagueName}>{item.league_name || item.league_id}</Text>
            {item.is_default ? <Text style={styles.defaultBadge}>Default</Text> : null}
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', paddingTop: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  email: { fontSize: 16, fontWeight: '600' },
  entitlement: { fontSize: 13, color: '#6b7280', marginTop: 2 },
  signOut: { color: '#dc2626', fontSize: 14 },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#6b7280',
    textTransform: 'uppercase',
    paddingHorizontal: 20,
    marginBottom: 8,
  },
  leagueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e5e7eb',
  },
  leagueName: { fontSize: 16 },
  defaultBadge: {
    fontSize: 12,
    color: '#2563eb',
    fontWeight: '600',
  },
  empty: {
    paddingHorizontal: 20,
    paddingTop: 12,
    color: '#6b7280',
  },
  error: {
    color: '#dc2626',
    paddingHorizontal: 20,
    marginBottom: 8,
  },
});
