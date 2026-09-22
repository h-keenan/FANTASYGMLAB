import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Modal,
  RefreshControl,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import GlassPanel from '../components/GlassPanel';
import IconCircle from '../components/IconCircle';
import PremiumLock from '../components/PremiumLock';
import { ApiError, api, type MeResponse, type SleeperLeagueOption } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useShowcaseMode } from '../context/ShowcaseModeContext';
import { getLastLeague } from '../lib/lastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { maskShowcaseFields, maskShowcaseText } from '../lib/showcaseMode';
import { supabase } from '../lib/supabase';
import { useThemeMode } from '../context/ThemeModeContext';
import { gradients, radii, spacing, typography, type ThemeColors } from '../theme';
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
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { session, signOut } = useAuth();
  const { showcaseMode } = useShowcaseMode();
  const [me, setMe] = useState<MeResponse['user'] | null>(null);
  const [leagues, setLeagues] = useState<SavedLeague[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [meError, setMeError] = useState<string | null>(null);
  const [leaguesError, setLeaguesError] = useState<string | null>(null);
  const [renamingLeague, setRenamingLeague] = useState<SavedLeague | null>(null);
  const [renameText, setRenameText] = useState('');
  const [renameBusy, setRenameBusy] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [addQuery, setAddQuery] = useState('');
  const [addBusy, setAddBusy] = useState(false);
  const [addOptions, setAddOptions] = useState<SleeperLeagueOption[] | null>(null);
  const [addMessage, setAddMessage] = useState<string | null>(null);
  // Set only when the server refuses a save with reason "at_cap" — the copy
  // is derived from the cap the server sent, never a hardcoded number.
  const [addCapMessage, setAddCapMessage] = useState<string | null>(null);
  const autoNavigated = useRef(false);

  // The cap is the server's (GET /v1/me -> league_cap, from
  // modules/saved_leagues.py), so mobile never carries its own copy of the
  // free/premium split. Missing/zero means "not known yet" — never treat an
  // unknown cap as a wall, or a slow /v1/me would look like a paywall.
  const leagueCap = me?.league_cap ?? 0;
  // profile_status "error" means `entitlement` is a fail-closed default, not
  // a known plan — never show a paying user an upgrade wall because a
  // profile read blipped. The server still enforces the cap on save.
  const atLeagueCap =
    leagueCap > 0 &&
    me?.profile_status === 'ok' &&
    me?.entitlement !== 'premium' &&
    (leagues?.length ?? 0) >= leagueCap;

  const closeAddLeague = () => {
    setAddOpen(false);
    setAddQuery('');
    setAddOptions(null);
    setAddMessage(null);
    setAddCapMessage(null);
  };

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
        // Saved leagues come straight from Supabase, not the API client, so
        // they miss authorizedRequest's showcase masking — apply it here.
        setLeagues(maskShowcaseFields((leaguesResult.value.data as SavedLeague[]) ?? []));
      }
    } else {
      setLeaguesError('Could not load your saved leagues.');
    }

    setLoading(false);
  }, []);

  // Sleeper league ids are long numeric strings, usernames never are — so a
  // purely numeric entry skips the username lookup and saves directly.
  const looksLikeLeagueId = (value: string) => /^\d{6,}$/.test(value);

  const saveLeague = async (input: { leagueId: string; leagueName?: string; username?: string }) => {
    setAddBusy(true);
    setAddMessage(null);
    setAddCapMessage(null);
    try {
      const result = await api.saveLeague({
        leagueId: input.leagueId,
        leagueName: input.leagueName ?? '',
        sleeperUsername: input.username ?? '',
      });
      if (result.ok) {
        closeAddLeague();
        await load();
        return;
      }
      if (result.reason === 'at_cap') {
        // Not an error state: the plan's league limit. Swap the picker for
        // the same upgrade card every other withheld-content surface uses.
        setAddOptions(null);
        setAddCapMessage(
          result.cap === 1
            ? 'Your plan keeps 1 saved league. Upgrade to Premium to manage all of your leagues here.'
            : `Your plan keeps ${result.cap} saved leagues. Upgrade to Premium to manage all of your leagues here.`,
        );
        return;
      }
      setAddMessage(
        result.reason === 'league_not_found'
          ? "That league isn't on Sleeper — check the league ID and try again."
          : 'Could not save that league right now. Please try again in a moment.',
      );
    } catch (error) {
      setAddMessage(
        error instanceof ApiError ? error.message : 'Could not reach the FantasyGM Lab API.',
      );
    } finally {
      setAddBusy(false);
    }
  };

  const findLeagues = async () => {
    const trimmed = addQuery.trim();
    if (!trimmed) {
      setAddMessage('Enter your Sleeper username, or a league ID.');
      return;
    }
    if (looksLikeLeagueId(trimmed)) {
      await saveLeague({ leagueId: trimmed });
      return;
    }
    setAddBusy(true);
    setAddMessage(null);
    setAddCapMessage(null);
    try {
      const result = await api.lookupSleeperLeagues(trimmed);
      setAddOptions(result.leagues);
      if (!result.ok || result.leagues.length === 0) {
        setAddMessage(result.message || 'No leagues found for that Sleeper username.');
      }
    } catch (error) {
      setAddOptions(null);
      setAddMessage(
        error instanceof ApiError ? error.message : 'Could not reach the FantasyGM Lab API.',
      );
    } finally {
      setAddBusy(false);
    }
  };

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
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  const defaultLeague = leagues?.find((league) => league.is_default) ?? leagues?.[0] ?? null;

  return (
    <View style={styles.container}>
      <LinearGradient colors={gradients.hero} style={styles.heroGradient} />

      <FlatList
        data={leagues ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />}
        ListHeaderComponent={
          <>
            <GlassPanel style={styles.header}>
              <View style={styles.headerRow}>
                <View style={styles.brandRow}>
                  <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
                  <View>
                    <AppText style={styles.brandName}>FantasyGM Lab</AppText>
                    <AppText style={styles.email}>
                      {session?.user.is_anonymous
                        ? 'Guest'
                        : maskShowcaseText('email', session?.user.email)}
                    </AppText>
                  </View>
                </View>
                <TouchableOpacity onPress={() => void signOut()} hitSlop={8}>
                  <AppText style={styles.signOut}>Sign out</AppText>
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
                  <AppText
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
                  </AppText>
                </TouchableOpacity>
              ) : null}
            </GlassPanel>

            {meError ? (
              <AppText style={styles.error}>Couldn't load your account: {meError}</AppText>
            ) : null}
            {leaguesError ? (
              <AppText style={styles.error}>Couldn't load your leagues: {leaguesError}</AppText>
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
                    <AppText style={styles.quickActionPrimaryLabel}>Continue in</AppText>
                  </View>
                  <AppText style={styles.quickActionPrimaryValue} numberOfLines={1}>
                    {defaultLeague.league_name || defaultLeague.league_id}
                  </AppText>
                </TouchableOpacity>
              ) : null}
              <TouchableOpacity style={styles.quickActionSecondary} onPress={() => navigation.navigate('News')}>
                <IconCircle name="globe-outline" color={colors.violet} iconSize={18} style={styles.quickActionIconCircle} />
                <AppText style={styles.quickActionSecondaryLabel}>News</AppText>
              </TouchableOpacity>
            </View>

            <View style={styles.sectionHeader}>
              <AppText style={styles.sectionTitle}>Your leagues</AppText>
              {atLeagueCap ? null : (
                <TouchableOpacity
                  style={styles.addLeagueButton}
                  onPress={() => {
                    setAddQuery(me?.sleeper_username ?? '');
                    setAddOpen(true);
                  }}
                  hitSlop={8}
                >
                  <Ionicons name="add" size={16} color={colors.accent} />
                  <AppText style={styles.addLeagueLabel}>Add league</AppText>
                </TouchableOpacity>
              )}
            </View>
            {atLeagueCap ? (
              <View style={styles.capLock}>
                <PremiumLock
                  title="Add another league"
                  description={
                    leagueCap === 1
                      ? 'Free accounts keep 1 saved league. Upgrade to manage all of your leagues here.'
                      : `Your plan keeps ${leagueCap} saved leagues. Upgrade to manage all of your leagues here.`
                  }
                />
              </View>
            ) : null}
          </>
        }
        ListEmptyComponent={
          <AppText style={styles.empty}>
            {leaguesError
              ? 'Could not check your saved leagues — pull to retry.'
              : 'No leagues saved yet. Tap “Add league” and enter your Sleeper username to get started.'}
          </AppText>
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
              <AppText style={styles.leagueName} numberOfLines={1}>
                {item.league_name || item.league_id}
              </AppText>
              {item.is_default ? (
                <View style={styles.defaultBadge}>
                  <AppText style={styles.defaultBadgeText}>Default</AppText>
                </View>
              ) : null}
              {/* Hidden while showcase mode is on: the name shown here is a
                  stand-in, and rename prefills from it — saving would write
                  the fake name back into saved_leagues for real. */}
              {showcaseMode ? null : (
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
              )}
              <AppText style={styles.chevron}>›</AppText>
            </View>
          </AnimatedCard>
        )}
      />

      <Modal visible={addOpen} animationType="fade" transparent onRequestClose={closeAddLeague}>
        <View style={styles.renameBackdrop}>
          <View style={styles.renameCard}>
            <AppText style={styles.renameTitle}>Add a league</AppText>
            <AppText style={styles.renameHint}>
              Enter your Sleeper username to pick from your leagues — or paste a league ID directly.
            </AppText>
            <TextInput
              style={styles.renameInput}
              value={addQuery}
              onChangeText={setAddQuery}
              placeholder="Sleeper username or league ID"
              placeholderTextColor={colors.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              editable={!addBusy}
              onSubmitEditing={() => void findLeagues()}
              returnKeyType="search"
              maxLength={64}
            />

            {addCapMessage ? (
              <View style={styles.capLockInModal}>
                <PremiumLock title="League limit reached" description={addCapMessage} />
              </View>
            ) : null}
            {addMessage ? <AppText style={styles.addError}>{addMessage}</AppText> : null}

            {addOptions && addOptions.length > 0 ? (
              <View style={styles.addOptions}>
                <AppText style={styles.addOptionsLabel}>Tap a league to save it</AppText>
                <FlatList
                  data={addOptions}
                  keyExtractor={(item) => item.league_id}
                  style={styles.addOptionsList}
                  keyboardShouldPersistTaps="handled"
                  renderItem={({ item }) => (
                    <TouchableOpacity
                      style={styles.addOptionRow}
                      disabled={addBusy}
                      onPress={() =>
                        void saveLeague({
                          leagueId: item.league_id,
                          leagueName: item.name,
                          username: addQuery.trim(),
                        })
                      }
                    >
                      <View style={styles.addOptionText}>
                        <AppText style={styles.addOptionName} numberOfLines={1}>
                          {item.name || item.league_id}
                        </AppText>
                        <AppText style={styles.addOptionMeta}>
                          {[item.season, item.total_rosters ? `${item.total_rosters} teams` : '']
                            .filter(Boolean)
                            .join(' · ')}
                        </AppText>
                      </View>
                      <AppText style={styles.chevron}>›</AppText>
                    </TouchableOpacity>
                  )}
                />
              </View>
            ) : null}

            <View style={styles.renameActions}>
              <TouchableOpacity
                style={styles.renameCancelButton}
                onPress={closeAddLeague}
                disabled={addBusy}
              >
                <AppText style={styles.renameCancelText}>Cancel</AppText>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.renameSaveButton}
                onPress={() => void findLeagues()}
                disabled={addBusy}
              >
                {addBusy ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <AppText style={styles.renameSaveText}>Find leagues</AppText>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={renamingLeague !== null} animationType="fade" transparent onRequestClose={() => setRenamingLeague(null)}>
        <View style={styles.renameBackdrop}>
          <View style={styles.renameCard}>
            <AppText style={styles.renameTitle}>Rename League</AppText>
            <AppText style={styles.renameHint}>
              Only changes what you see here — the real league name in Sleeper stays the same.
            </AppText>
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
                <AppText style={styles.renameCancelText}>Cancel</AppText>
              </TouchableOpacity>
              <TouchableOpacity style={styles.renameSaveButton} onPress={saveLeagueRename} disabled={renameBusy}>
                {renameBusy ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <AppText style={styles.renameSaveText}>Save</AppText>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
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
    borderColor: colors.cardBorder,
  },
  quickActionSecondaryLabel: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  quickActionIconCircle: { marginBottom: 2 },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingRight: spacing.sm,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm,
  },
  addLeagueButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    backgroundColor: colors.accentMuted,
  },
  addLeagueLabel: { fontSize: 12, fontWeight: '700', color: colors.accent },
  capLock: { marginBottom: spacing.sm },
  capLockInModal: { marginTop: spacing.md },
  addError: { fontSize: 12, color: colors.danger, marginTop: spacing.sm, lineHeight: 16 },
  addOptions: { marginTop: spacing.md },
  addOptionsLabel: {
    ...typography.kicker,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    marginBottom: spacing.xs,
  },
  // Bounded so a manager with a dozen leagues still sees the action row
  // below the list instead of a modal that runs off the screen.
  addOptionsList: { maxHeight: 220 },
  addOptionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  addOptionText: { flex: 1, marginRight: spacing.sm },
  addOptionName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  addOptionMeta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
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
    borderColor: colors.cardBorder,
    padding: spacing.lg,
  },
  renameTitle: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
  renameHint: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 16 },
  renameInput: {
    borderWidth: 1,
    borderColor: colors.cardBorder,
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
}
