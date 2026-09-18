import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Modal,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import GlassPanel from '../components/GlassPanel';
import { api, type MeResponse } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { getLastLeague } from '../lib/lastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { supabase } from '../lib/supabase';
import { colors, gradients, radii, spacing, typography } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

interface SavedLeague {
  id: string;
  league_id: string;
  league_name: string;
  is_default: boolean;
}

export default function HomeScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { session, signOut } = useAuth();
  const [me, setMe] = useState<MeResponse['user'] | null>(null);
  const [leagues, setLeagues] = useState<SavedLeague[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [meError, setMeError] = useState<string | null>(null);
  const [leaguesError, setLeaguesError] = useState<string | null>(null);
  const [renamingLeague, setRenamingLeague] = useState<SavedLeague | null>(null);
  const [renameText, setRenameText] = useState('');
  const [renameBusy, setRenameBusy] = useState(false);
  const autoNavigated = useRef(false);

  // Renames only this account's saved_leagues row (RLS-scoped to
  // auth.uid() = user_id) — never touches the Sleeper league itself, so
  // nothing about the real league name changes for anyone else.
  const saveLeagueRename = async () => {
    if (!renamingLeague) return;
    const trimmed = renameText.trim();
    if (!trimmed) {
      Alert.alert('Name required', 'League name cannot be empty.');
      return;
    }
    setRenameBusy(true);
    try {
      const { error } = await supabase
        .from('saved_leagues')
        .update({ league_name: trimmed })
        .eq('id', renamingLeague.id);
      if (error) {
        Alert.alert('Could not rename league', error.message);
        return;
      }
      setLeagues((prev) =>
        (prev ?? []).map((league) =>
          league.id === renamingLeague.id ? { ...league, league_name: trimmed } : league,
        ),
      );
      setRenamingLeague(null);
    } catch {
      Alert.alert('Could not rename league', 'Please try again in a moment.');
    } finally {
      setRenameBusy(false);
    }
  };

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

  // useFocusEffect (not a plain mount effect) so returning here after a
  // Premium purchase (Paywall -> goBack) or an entitlement change made
  // elsewhere re-fetches /v1/me instead of showing stale Free/Premium state.
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  // Skip the "pick a league" step on repeat visits: jump straight into the
  // last league opened (or the marked default) once, on first load. Home
  // stays reachable afterward via the GM Orb, so this never traps anyone.
  useEffect(() => {
    if (autoNavigated.current || !leagues || leagues.length === 0) return;
    autoNavigated.current = true;
    (async () => {
      const last = await getLastLeague();
      const target =
        (last ? leagues.find((league) => league.league_id === last.leagueId) : null) ??
        leagues.find((league) => league.is_default) ??
        null;
      if (target) {
        navigation.navigate('Dashboard', {
          leagueId: target.league_id,
          leagueName: target.league_name || 'League',
        });
      }
    })();
  }, [leagues, navigation]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  const defaultLeague = leagues?.find((league) => league.is_default) ?? leagues?.[0] ?? null;

  return (
    <View style={styles.container}>
      <LinearGradient colors={gradients.hero} style={styles.heroGradient} />

      <FlatList
        data={leagues ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />}
        ListHeaderComponent={
          <>
            <GlassPanel style={styles.header}>
              <View style={styles.headerRow}>
                <View style={styles.brandRow}>
                  <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
                  <View>
                    <Text style={styles.brandName}>FantasyGM Lab</Text>
                    <Text style={styles.email}>{session?.user.is_anonymous ? 'Guest' : session?.user.email}</Text>
                  </View>
                </View>
                <TouchableOpacity onPress={() => void signOut()} hitSlop={8}>
                  <Text style={styles.signOut}>Sign out</Text>
                </TouchableOpacity>
              </View>
              {me ? (
                <TouchableOpacity
                  disabled={me.entitlement === 'premium'}
                  onPress={() => (me.profile_status === 'error' ? void load() : navigation.navigate('Paywall'))}
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
                    {me.profile_status === 'error'
                      ? "Couldn't verify your plan — tap to retry"
                      : me.entitlement === 'premium'
                        ? 'Premium'
                        : 'Free — Upgrade'}
                  </Text>
                </TouchableOpacity>
              ) : null}
            </GlassPanel>

            {meError ? (
              <Text style={styles.error}>Couldn't load your account: {meError}</Text>
            ) : null}
            {leaguesError ? (
              <Text style={styles.error}>Couldn't load your leagues: {leaguesError}</Text>
            ) : null}

            <View style={styles.quickActions}>
              {defaultLeague ? (
                <TouchableOpacity
                  style={styles.quickActionPrimary}
                  onPress={() =>
                    navigation.navigate('Dashboard', {
                      leagueId: defaultLeague.league_id,
                      leagueName: defaultLeague.league_name || 'League',
                    })
                  }
                >
                  <View style={styles.quickActionPrimaryRow}>
                    <Ionicons name="grid-outline" size={16} color={colors.accentSoft} />
                    <Text style={styles.quickActionPrimaryLabel}>Continue in</Text>
                  </View>
                  <Text style={styles.quickActionPrimaryValue} numberOfLines={1}>
                    {defaultLeague.league_name || defaultLeague.league_id}
                  </Text>
                </TouchableOpacity>
              ) : null}
              <TouchableOpacity style={styles.quickActionSecondary} onPress={() => navigation.navigate('News')}>
                <Ionicons name="globe-outline" size={20} color={colors.textPrimary} />
                <Text style={styles.quickActionSecondaryLabel}>News</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.sectionTitle}>Your leagues</Text>
          </>
        }
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
              navigation.navigate('Dashboard', {
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
              <TouchableOpacity
                hitSlop={8}
                style={styles.renameButton}
                onPress={() => {
                  setRenamingLeague(item);
                  setRenameText(item.league_name || '');
                }}
              >
                <Ionicons name="pencil-outline" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
              <Text style={styles.chevron}>›</Text>
            </View>
          </AnimatedCard>
        )}
      />

      <Modal visible={renamingLeague !== null} animationType="fade" transparent onRequestClose={() => setRenamingLeague(null)}>
        <View style={styles.renameBackdrop}>
          <View style={styles.renameCard}>
            <Text style={styles.renameTitle}>Rename League</Text>
            <Text style={styles.renameHint}>
              Only changes what you see here — the real league name in Sleeper stays the same.
            </Text>
            <TextInput
              style={styles.renameInput}
              value={renameText}
              onChangeText={setRenameText}
              placeholder="League name"
              placeholderTextColor={colors.textTertiary}
              autoFocus
              maxLength={80}
            />
            <View style={styles.renameActions}>
              <TouchableOpacity
                style={styles.renameCancelButton}
                onPress={() => setRenamingLeague(null)}
                disabled={renameBusy}
              >
                <Text style={styles.renameCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.renameSaveButton} onPress={saveLeagueRename} disabled={renameBusy}>
                {renameBusy ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.renameSaveText}>Save</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
  heroGradient: { position: 'absolute', top: 0, left: 0, right: 0, height: 220 },
  header: {
    marginHorizontal: spacing.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    marginBottom: spacing.lg,
  },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  brandMark: { width: 40, height: 40, borderRadius: radii.sm },
  brandName: { ...typography.label, color: colors.textSecondary, letterSpacing: 0.4 },
  email: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginTop: 2 },
  entitlementPill: {
    alignSelf: 'flex-start',
    marginTop: spacing.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: radii.pill,
    backgroundColor: colors.accentMuted,
  },
  entitlementPillPremium: {
    backgroundColor: colors.premiumMuted,
  },
  entitlementText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  entitlementTextPremium: { color: colors.premium },
  signOut: { color: colors.danger, fontSize: 14, fontWeight: '500' },
  quickActions: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.xl,
  },
  quickActionPrimary: {
    flex: 2,
    backgroundColor: colors.accentMuted,
    borderRadius: radii.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.accent,
  },
  quickActionPrimaryRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  quickActionPrimaryLabel: { fontSize: 11, fontWeight: '600', color: colors.accentSoft, textTransform: 'uppercase' },
  quickActionPrimaryValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginTop: 2 },
  quickActionSecondary: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    padding: spacing.md,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  quickActionSecondaryLabel: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
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
    paddingBottom: spacing.xl * 3,
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
  renameButton: { marginLeft: spacing.sm, padding: 2 },
  chevron: { fontSize: 20, color: colors.textTertiary, marginLeft: spacing.xs },
  renameBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  renameCard: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  renameTitle: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
  renameHint: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 16 },
  renameInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
  },
  renameActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  renameCancelButton: { paddingHorizontal: spacing.md, paddingVertical: 10 },
  renameCancelText: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
  renameSaveButton: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.lg,
    paddingVertical: 10,
    borderRadius: radii.sm,
    minWidth: 64,
    alignItems: 'center',
  },
  renameSaveText: { fontSize: 14, fontWeight: '700', color: '#fff' },
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
