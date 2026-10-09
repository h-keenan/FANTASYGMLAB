import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Linking,
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

import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import GlassPanel from '../components/GlassPanel';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import LeaguesGlanceSection from '../components/LeaguesGlanceSection';
import PremiumLock from '../components/PremiumLock';
import { ApiError, api, type MeResponse, type SleeperLeagueOption } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useOnboarding } from '../context/OnboardingContext';
import { useShowcaseMode } from '../context/ShowcaseModeContext';
import { getLastLeague } from '../lib/lastLeague';
import { glanceSectionState } from '../lib/leaguesGlance';
import { useOrbClearance } from '../lib/orbLayout';
import { maskShowcaseFields, maskShowcaseText } from '../lib/showcaseMode';
import { supabase } from '../lib/supabase';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, typography, type ThemeColors } from '../theme';
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
  const { consumeFirstLeagueTeamStanceRouting } = useOnboarding();
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
  // Fix (welcome audit, tester feedback "I don't even know where to start"):
  // a brand-new user with no existing Sleeper account/league has no path
  // forward on this screen otherwise — this toggles the honest "we don't
  // host leagues, here's where to make one" explainer. Also auto-opened
  // below the moment a real search comes back empty, so the explanation
  // appears exactly when it's needed, not only for someone who happens to
  // notice the persistent link first.
  const [showNoLeagueHelp, setShowNoLeagueHelp] = useState(false);
  // Set only when the server refuses a save with reason "at_cap" — the copy
  // is derived from the cap the server sent, never a hardcoded number.
  const [addCapMessage, setAddCapMessage] = useState<string | null>(null);
  const autoNavigated = useRef(false);
  // Bumped on every load() (focus + pull-to-refresh) so the "All leagues at
  // a glance" section re-reads its server-cached cards alongside the rest.
  const [glanceReloadToken, setGlanceReloadToken] = useState(0);

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

  // Cross-league glance cards: Premium with 2+ saved leagues gets the real
  // section above the league list; Free gets a locked teaser below it
  // (Free keeps one league, so there's nothing to compare yet).
  const glanceState = glanceSectionState({
    entitlement: me?.entitlement,
    profileStatus: me?.profile_status,
    savedLeagueCount: leagues?.length ?? 0,
  });

  const closeAddLeague = () => {
    setAddOpen(false);
    setAddQuery('');
    setAddOptions(null);
    setAddMessage(null);
    setAddCapMessage(null);
    setShowNoLeagueHelp(false);
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
    setGlanceReloadToken((token) => token + 1);

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
        // Fix 1 (welcome/signup audit): a genuine-first-run onboarding
        // "Get Started" arms this signal (OnboardingContext), and this is
        // the user's very first league ever (none existed before this
        // save) — route into Team Situation instead of the usual "stay on
        // Home" / auto-jump-to-Dashboard behavior, honoring onboarding's
        // "tell us your team's situation" promise. Pre-arm autoNavigated so
        // the effect below never races this with its own Dashboard jump.
        const wasFirstLeagueEver = (leagues?.length ?? 0) === 0;
        const routeToTeamStance = wasFirstLeagueEver && consumeFirstLeagueTeamStanceRouting();
        if (routeToTeamStance) autoNavigated.current = true;
        closeAddLeague();
        await load();
        if (routeToTeamStance) {
          navigation.navigate('TeamStance', {
            leagueId: input.leagueId,
            leagueName: input.leagueName || 'League',
          });
        }
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
        // A real zero-result search is exactly the moment someone with no
        // Sleeper account/league actually needs this explanation — surface
        // it automatically rather than relying on them to notice the
        // persistent link themselves.
        setShowNoLeagueHelp(true);
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

  // Skip the "pick a league" step on repeat visits, once on first load. Home
  // stays reachable afterward via the GM Orb, so this never traps anyone.
  // Exactly one saved league: jump straight into that league's Dashboard
  // (unchanged). Two or more: land on the cross-league Portfolio view
  // instead of guessing which single league to jump into (coridian_-
  // approved) — Portfolio's own row-tap (PortfolioScreen's openLeague)
  // still reaches any one league's Dashboard directly, just one tap
  // further than the old single-league auto-jump below.
  useEffect(() => {
    if (autoNavigated.current || !leagues || leagues.length === 0) return;
    autoNavigated.current = true;
    if (leagues.length > 1) {
      navigation.navigate('Portfolio');
      return;
    }
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
      <GridBackground />

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
                <AnimatedCard
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
                </AnimatedCard>
              ) : null}
              <AnimatedCard style={styles.quickActionSecondary} onPress={() => navigation.navigate('News')}>
                <IconCircle name="globe-outline" color={colors.violet} iconSize={18} style={styles.quickActionIconCircle} />
                <AppText style={styles.quickActionSecondaryLabel}>News</AppText>
              </AnimatedCard>
            </View>

            {glanceState === 'active' ? (
              <LeaguesGlanceSection state="active" reloadToken={glanceReloadToken} />
            ) : null}

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
        ListFooterComponent={
          glanceState === 'locked' ? (
            <View style={styles.glanceTeaser}>
              <LeaguesGlanceSection state="locked" reloadToken={glanceReloadToken} />
            </View>
          ) : null
        }
        ListEmptyComponent={
          <EmptyState
            icon={leaguesError ? 'cloud-offline-outline' : 'shield-outline'}
            title={leaguesError ? "Couldn't load your leagues" : 'No leagues yet'}
            subtitle={
              leaguesError
                ? 'Pull down to retry.'
                : 'Add your Sleeper league to start getting GM recommendations.'
            }
            actionLabel={!leaguesError && !atLeagueCap ? 'Add league' : undefined}
            onPressAction={
              !leaguesError && !atLeagueCap
                ? () => {
                    setAddQuery(me?.sleeper_username ?? '');
                    setAddOpen(true);
                  }
                : undefined
            }
            // Same gap this fixes everywhere else on this screen: a user
            // with zero saved leagues lands on exactly this empty state —
            // give them the explainer from here too, not only from inside
            // the modal they'd have to already know to open.
            secondaryLabel={!leaguesError ? "Don't have a Sleeper league yet?" : undefined}
            onPressSecondary={
              !leaguesError
                ? () => {
                    setAddQuery(me?.sleeper_username ?? '');
                    setAddOpen(true);
                    setShowNoLeagueHelp(true);
                  }
                : undefined
            }
          />
        }
        renderItem={({ item, index }) => {
          const isFirst = index === 0;
          const isLast = index === (leagues?.length ?? 0) - 1;
          return (
            <TouchableOpacity
              activeOpacity={0.7}
              style={[
                styles.leagueRow,
                isFirst && styles.leagueRowFirst,
                isLast && styles.leagueRowLast,
                !isLast && styles.leagueRowDivider,
              ]}
              onPress={() =>
                navigation.navigate('Dashboard', {
                  leagueId: item.league_id,
                  leagueName: item.league_name || 'League',
                })
              }
            >
              <IconCircle name="shield-outline" color={colors.accent} size={36} iconSize={17} style={styles.leagueIcon} />
              <View style={styles.leagueTextGroup}>
                <View style={styles.leagueNameRow}>
                  <AppText style={styles.leagueName} numberOfLines={1}>
                    {item.league_name || item.league_id}
                  </AppText>
                  {item.is_default ? (
                    <View style={styles.defaultBadge}>
                      <AppText style={styles.defaultBadgeText}>Default</AppText>
                    </View>
                  ) : null}
                </View>
              </View>
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
              <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
            </TouchableOpacity>
          );
        }}
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

            {/* Fix (welcome audit): a persistent, always-available affordance
                for a brand-new user who has no Sleeper account/league at
                all — not only shown reactively after a failed search (see
                findLeagues' auto-expand above), since someone might never
                attempt a search in the first place without this nudge. */}
            <TouchableOpacity
              onPress={() => setShowNoLeagueHelp((value) => !value)}
              hitSlop={8}
              style={styles.noLeagueToggle}
            >
              <AppText style={styles.noLeagueToggleText}>Don't have a Sleeper league yet?</AppText>
              <Ionicons
                name={showNoLeagueHelp ? 'chevron-up' : 'chevron-down'}
                size={14}
                color={colors.textSecondary}
              />
            </TouchableOpacity>
            {showNoLeagueHelp ? (
              <View style={styles.noLeagueCard}>
                <AppText style={styles.noLeagueText}>
                  FantasyGM Lab is a GM assistant for a league you already have on Sleeper — it
                  doesn't create or host leagues itself. Create a free league in the Sleeper app
                  (or at sleeper.com), then come back here and search your Sleeper username.
                </AppText>
                <TouchableOpacity
                  style={styles.noLeagueButton}
                  onPress={() => void Linking.openURL('https://sleeper.com')}
                >
                  <AppText style={styles.noLeagueButtonText}>Open Sleeper</AppText>
                  <Ionicons name="open-outline" size={14} color={colors.accent} />
                </TouchableOpacity>
              </View>
            ) : null}

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
                      <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
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
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
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
  // Left accent rail (not a full glow rim — that variant wraps itself in an
  // outer gradient that ignores the flex ratio a fixed 2:1 row here needs)
  // marks this as the strongest action on the screen, matching TeamsScreen's
  // rowMine treatment: cyan reserved for "this one matters" (§14).
  quickActionPrimary: {
    flex: 2,
    padding: spacing.md,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
  },
  quickActionPrimaryRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  quickActionPrimaryLabel: { fontSize: 11, fontWeight: '600', color: colors.accentSoft, textTransform: 'uppercase' },
  quickActionPrimaryValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginTop: 2 },
  quickActionSecondary: {
    flex: 1,
    padding: spacing.md,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 2,
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
  glanceTeaser: { marginTop: spacing.xl },
  capLockInModal: { marginTop: spacing.md },
  addError: { fontSize: 12, color: colors.danger, marginTop: spacing.sm, lineHeight: 16 },
  noLeagueToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    marginTop: spacing.md,
  },
  noLeagueToggleText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  noLeagueCard: {
    marginTop: spacing.sm,
    padding: spacing.md,
    borderRadius: radii.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  noLeagueText: { fontSize: 12, color: colors.textSecondary, lineHeight: 17 },
  noLeagueButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    marginTop: spacing.sm,
  },
  noLeagueButtonText: { fontSize: 13, fontWeight: '700', color: colors.accent },
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
  },
  // Continuous grouped surface with internal dividers (Magna Carta §12)
  // instead of a separately-bordered, separately-animated card per league —
  // every saved league is a peer row in one list, not N independent
  // modules (matches TeamsScreen/PlayersScreen's row treatment).
  leagueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
    borderRightWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
  },
  leagueRowFirst: {
    borderTopWidth: StyleSheet.hairlineWidth * 1.5,
    borderTopLeftRadius: radii.md,
    borderTopRightRadius: radii.md,
  },
  leagueRowLast: {
    borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
    borderBottomLeftRadius: radii.md,
    borderBottomRightRadius: radii.md,
  },
  leagueRowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  leagueIcon: { marginRight: spacing.sm },
  leagueTextGroup: { flex: 1, marginRight: spacing.sm },
  leagueNameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  leagueName: { flexShrink: 1, fontSize: 16, fontWeight: '500', color: colors.textPrimary },
  defaultBadge: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  defaultBadgeText: { fontSize: 11, fontWeight: '700', color: '#fff' },
  renameButton: { marginLeft: spacing.sm, marginRight: spacing.sm, padding: 2 },
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
  error: {
    color: colors.danger,
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm,
  },
  });
}
