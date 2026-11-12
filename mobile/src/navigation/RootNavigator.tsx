import React, { useEffect, useRef, useState } from 'react';
import { InteractionManager, TouchableOpacity, View } from 'react-native';
import AppBackground from '../components/AppBackground';
import { DarkTheme, DefaultTheme, NavigationContainer, type Theme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import type { CollegeProspect, DraftPickAsset, RankedPlayer } from '../lib/api';
import HeaderBackdrop from '../components/HeaderBackdrop';
import BrandMark from '../components/BrandMark';
import GmOrb from '../components/GmOrb';
import TradeOutcomePrompt from '../components/TradeOutcomePrompt';
import GuessThePlayerPrompt from '../components/GuessThePlayerPrompt';
import GuessThePlayerNameMatchPrompt from '../components/GuessThePlayerNameMatchPrompt';
import { navigationRef } from './navigationRef';

import { useAuth } from '../context/AuthContext';
import { useOnboarding } from '../context/OnboardingContext';
import { useThemeMode } from '../context/ThemeModeContext';
import LoginScreen from '../screens/LoginScreen';
import HomeScreen from '../screens/HomeScreen';
import { createLegacyRedirectScreen } from '../components/LegacyRouteRedirect';
import { PlayerQuickViewProvider } from '../context/PlayerQuickViewContext';
import type { OfferPrefill } from '../lib/tradeOffer';
import type { MultiTransfer } from '../lib/multiTeamTrade';
import LoadingScreen from '../screens/LoadingScreen';
import EspnUnavailableScreen from '../components/EspnUnavailableScreen';
import { isEspnLeagueId } from '../lib/leaguePlatform';
import { trackScreen } from '../lib/analytics';
import { isLegacyRedirectRoute } from '../lib/homeRedirects';
import { createLazyLoader, preloadInSequence, type LazyLoader } from '../lib/lazyModule';


// Screens are required on first render instead of at launch: every static
// `import` of a screen used to evaluate that screen and everything only it
// imports before the first frame (Metro's inlineRequires is off), although a
// session opens one or two of them. Home, Login and Loading stay eager (first
// frame); the top destinations are warmed at idle time below (see
// `preloadTopScreens`). See docs/performance-audit-client-2026-11.md.
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- screens take different param lists
function lazyScreen(load: () => { default: React.ComponentType<any> }): React.ComponentType<any> & { loader: LazyLoader<React.ComponentType<any>> } {
  const loader = createLazyLoader(() => load().default);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function LazyScreen(props: any) {
    const Screen = loader.get();
    return <Screen {...props} />;
  }
  LazyScreen.loader = loader;
  return LazyScreen;
}

/* eslint-disable @typescript-eslint/no-require-imports */
const OnboardingScreen = lazyScreen(() => require('../screens/OnboardingScreen'));
const TeamRosterScreen = lazyScreen(() => require('../screens/TeamRosterScreen'));
const PaywallScreen = lazyScreen(() => require('../screens/PaywallScreen'));
const TrialLapsedScreen = lazyScreen(() => require('../screens/TrialLapsedScreen'));
const NewsScreen = lazyScreen(() => require('../screens/NewsScreen'));
const DesignScreen = lazyScreen(() => require('../screens/DesignScreen'));
const SampleLeagueScreen = lazyScreen(() => require('../screens/SampleLeagueScreen'));
const MoreScreen = lazyScreen(() => require('../screens/MoreScreen'));
const LegalPageScreen = lazyScreen(() => require('../screens/LegalPageScreen'));
const HowWeEvaluateScreen = lazyScreen(() => require('../screens/HowWeEvaluateScreen'));
const PlayersScreen = lazyScreen(() => require('../screens/PlayersScreen'));
const PlayerDetailScreen = lazyScreen(() => require('../screens/PlayerDetailScreen'));
const PlayerCompareScreen = lazyScreen(() => require('../screens/PlayerCompareScreen'));
const WaiversScreen = lazyScreen(() => require('../screens/WaiversScreen'));
const RecapScreen = lazyScreen(() => require('../screens/RecapScreen'));
const AlertsScreen = lazyScreen(() => require('../screens/AlertsScreen'));
const GmPlanScreen = lazyScreen(() => require('../screens/GmPlanScreen'));
const TradeHistoryScreen = lazyScreen(() => require('../screens/TradeHistoryScreen'));
const CommunityScreen = lazyScreen(() => require('../screens/CommunityScreen'));
const FeaturesScreen = lazyScreen(() => require('../screens/FeaturesScreen'));
const DashboardScreen = lazyScreen(() => require('../screens/DashboardScreen'));
const TradesScreen = lazyScreen(() => require('../screens/TradesScreen'));
const TradeOfferScreen = lazyScreen(() => require('../screens/TradeOfferScreen'));
const TeamsScreen = lazyScreen(() => require('../screens/TeamsScreen'));
const GamesScreen = lazyScreen(() => require('../screens/GamesScreen'));
const CommissionerScreen = lazyScreen(() => require('../screens/CommissionerScreen'));
const DraftCenterScreen = lazyScreen(() => require('../screens/DraftCenterScreen'));
const FantasySimScreen = lazyScreen(() => require('../screens/FantasySimScreen'));
const PickDetailScreen = lazyScreen(() => require('../screens/PickDetailScreen'));
const MyTeamScreen = lazyScreen(() => require('../screens/MyTeamScreen'));
const MatchupScreen = lazyScreen(() => require('../screens/MatchupScreen'));
const CollegeProspectsScreen = lazyScreen(() => require('../screens/CollegeProspectsScreen'));
const ProspectScoutingDetailScreen = lazyScreen(() => require('../screens/ProspectScoutingDetailScreen'));
const PortfolioScreen = lazyScreen(() => require('../screens/PortfolioScreen'));
const GmGameScreen = lazyScreen(() => require('../screens/GmGameScreen'));
const FounderAnalyticsScreen = lazyScreen(() => require('../screens/FounderAnalyticsScreen'));
const LiveDraftScreen = lazyScreen(() => require('../screens/LiveDraftScreen'));
const GuessThePlayerLeaderboardScreen = lazyScreen(() => require('../screens/GuessThePlayerLeaderboardScreen'));
/* eslint-enable @typescript-eslint/no-require-imports */

export type RootStackParamList = {
  /** `openAddLeague`: opens Home's Add League sheet on arrival (the header
   * league switcher's "Add a league" row). */
  Home: { openAddLeague?: boolean } | undefined;
  Onboarding: { replay?: boolean } | undefined;
  LeagueDetail: { leagueId: string; leagueName: string };
  TeamRoster: { ownerName: string; playerIds: string[]; leagueId: string; leagueName: string; rosterId: string };
  /** `fromOnboarding`: shown as the first-run trial offer right after the
   * intro carousel (web-next's OnboardingPaywall step), so closing it means
   * "continue free" and finishes onboarding. 'getStarted' = finished the
   * carousel (arms Team Situation routing), 'skip' = skipped it. */
  Paywall: { fromOnboarding?: 'getStarted' | 'skip' } | undefined;
  TrialLapsed: undefined;
  /** playerId/playerName filter the feed to one player's news (quick view's "See all news"). */
  News: { playerId?: string; playerName?: string } | undefined;
  More: undefined;
  /** Hidden design-system reference; reachable only by long-pressing the Legal heading on More. */
  Design: undefined;
  /** Static fictional demo league for users with no league connected yet. */
  SampleLeague: undefined;
  LegalPage: { pageKey: string };
  HowWeEvaluate: undefined;
  Players: { leagueId: string; leagueName: string };
  PlayerDetail: {
    player: RankedPlayer;
    leagueId: string;
    leagueName: string;
    /** Tab to open on (the quick view's "See all news" opens 'news'). */
    initialTab?: 'stats' | 'trends' | 'schedule' | 'career' | 'model' | 'news';
  };
  PlayerCompare: { player: RankedPlayer; leagueId: string; leagueName: string };
  GmTargets: { leagueId: string; leagueName: string };
  TeamStance: { leagueId: string; leagueName: string };
  GmPlan: { leagueId: string; leagueName: string; initialTab?: 'overview' | 'trades' | 'core' | 'watching' };
  TradeHistory: undefined;
  Community: undefined;
  /** "What FantasyDesk can do". League params only when a link carries one (else the last league). */
  Features: { leagueId?: string; leagueName?: string } | undefined;
  Waivers: { leagueId: string; leagueName: string; playerId?: string; tab?: 'recommended' | 'explore' | 'watchlist' };
  Recap: { leagueId: string; leagueName: string; initialTab?: 'recap' | 'roundup'; week?: number };
  Dashboard: { leagueId: string; leagueName: string };
  // Single consolidated host for Trade Hub ("Hub"), Trade Finder
  // ("Finder"), and Trade Analyzer ("Analyzer") — see TradesScreen.
  // `initialTab` defaults to 'block' when omitted. `tradePlayer` is the
  // player a PlayerDetail / Players "Add to Trade" or "Find trades" shortcut
  // started from: 'make' files them on the right side of Trade Analyzer,
  // 'search' pre-selects them in Trade Finder and runs the search.
  Trades: {
    leagueId: string;
    leagueName: string;
    initialTab?: 'block' | 'search' | 'make';
    tradePlayer?: RankedPlayer;
    // A built offer ("Build an offer") loaded into the Analyzer tab to tweak/share.
    offerPrefill?: OfferPrefill;
    // A 3-team idea from Trade Hub, loaded into the Analyzer's Multi-team builder and graded.
    multiPrefill?: MultiTransfer[];
  };
  // "Build an offer": 2-3 built packages to get a player off another team.
  TradeOffer: { leagueId: string; leagueName: string; playerId: string };
  // `metric` picks which TeamRanking rank field the leaderboard sorts/labels
  // by (defaults to 'power' when omitted, matching every pre-existing
  // caller) — added so My Team's Age tile (TeamAnalysisPanel) can drill
  // into a real per-team Age tier list via this same shared leaderboard
  // instead of needing a standalone screen.
  Teams: {
    leagueId: string;
    leagueName: string;
    metric?: 'power' | 'franchise' | 'draft_capital' | 'starter' | 'bench' | 'age';
    // League Rankings hosts two tabs (Rankings / Playoff Odds); defaults to
    // 'rankings'. Ignored for ESPN leagues, which only have Rankings.
    initialTab?: 'rankings' | 'playoff';
  };
  // Retired: Playoff Odds is now the 'playoff' tab of Teams. Kept registered
  // as a redirect (see lib/homeRedirects.ts) so deep links and stale nav
  // state still resolve.
  PlayoffOdds: { leagueId: string; leagueName: string };
  Games: { leagueId: string; leagueName: string; tab?: 'sim' | 'pickem' };
  Commissioner: { leagueId: string; leagueName: string };
  DraftCenter: { leagueId: string; leagueName: string; tab?: 'overview' | 'picks' | 'scouting' };
  FantasySim: { leagueId: string; leagueName: string };
  PickDetail: { pick: DraftPickAsset; leagueId: string; leagueName: string };
  MyTeam: { leagueId: string; leagueName: string };
  Matchup: { leagueId: string; leagueName: string };
  Alerts: { leagueId: string; leagueName: string };
  // Not league-scoped — shared prospect pool + personal watchlist span every league.
  CollegeProspects: undefined;
  CollegeProspectDetail: { prospect: CollegeProspect };
  // Not league-scoped — the whole point is standing/needs across every
  // saved league at once, not one league's context.
  Portfolio: undefined;
  GmGame: undefined;
  // Founder-only (server enforces founder_ops; the screen also bounces non-founders).
  FounderAnalytics: undefined;
  // Sleeper-only (gated like the other league screens) — read-only draft room.
  LiveDraft: { leagueId: string; leagueName: string };
  GuessThePlayerLeaderboard: { leagueId: string; leagueName: string };
};

const AppStack = createNativeStackNavigator<RootStackParamList>();

/**
 * ESPN leagues (league id "espn:{id}:{season}", lib/leaguePlatform.ts) can
 * feed only some league screens. Every other league screen is registered
 * through this wrapper, which shows EspnUnavailableScreen for an ESPN
 * league instead of loading a Sleeper-only screen. One check here instead
 * of a copy per screen; Sleeper leagues render the screen unchanged.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- wraps screens with different param lists
function withEspnGate(Screen: React.ComponentType<any>): React.ComponentType<any> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function EspnGatedScreen(props: any) {
    const params = (props.route?.params ?? {}) as { leagueId?: string; leagueName?: string };
    if (isEspnLeagueId(params.leagueId)) {
      return <EspnUnavailableScreen leagueId={params.leagueId as string} leagueName={params.leagueName || 'This league'} />;
    }
    return <Screen {...props} />;
  }
  return EspnGatedScreen;
}

// Retired routes kept as redirects (deep links, push taps, stale nav state):
// League Overview -> Dashboard, GM Targets / Team Situation -> GM Plan tabs.
const LeagueDetailRedirect = createLegacyRedirectScreen('LeagueDetail');
const GmTargetsRedirect = createLegacyRedirectScreen('GmTargets');
const TeamStanceRedirect = createLegacyRedirectScreen('TeamStance');
const PlayoffOddsRedirect = createLegacyRedirectScreen('PlayoffOdds');
const EspnWaiversScreen = withEspnGate(WaiversScreen);
const EspnRecapScreen = withEspnGate(RecapScreen);
const EspnDashboardScreen = withEspnGate(DashboardScreen);
const EspnGamesScreen = withEspnGate(GamesScreen);
const EspnCommissionerScreen = withEspnGate(CommissionerScreen);
const EspnDraftCenterScreen = withEspnGate(DraftCenterScreen);
const EspnFantasySimScreen = withEspnGate(FantasySimScreen);
const EspnPickDetailScreen = withEspnGate(PickDetailScreen);
const EspnMatchupScreen = withEspnGate(MatchupScreen);
const EspnAlertsScreen = withEspnGate(AlertsScreen);
const EspnGmPlanScreen = withEspnGate(GmPlanScreen);
const EspnLiveDraftScreen = withEspnGate(LiveDraftScreen);
const EspnGuessLeaderboardScreen = withEspnGate(GuessThePlayerLeaderboardScreen);
const AuthStack = createNativeStackNavigator();

// The destinations most sessions open first, warmed one per turn once the
// first screen has settled so tapping them does not pay their module
// evaluation. Everything else loads on first open.
const TOP_SCREEN_LOADERS = [DashboardScreen, TradesScreen, PlayersScreen, GmPlanScreen, WaiversScreen].map(
  (screen) => screen.loader,
);
const PRELOAD_GAP_MS = 150;

export default function RootNavigator() {
  const { session, loading } = useAuth();
  const { onboardingComplete } = useOnboarding();
  const { colors, isDark } = useThemeMode();
  // Tracked purely so the GM orb / trade-outcome prompt can hide themselves
  // while the first-launch tutorial is the active screen — slide 3 already
  // explains the orb as a static stand-in, and letting the real (tappable,
  // stateful) orb float over the other four slides would be a distracting
  // duplicate of what the screen is teaching. Neither GmOrb nor
  // TradeOutcomePrompt is otherwise touched.
  const [currentRouteName, setCurrentRouteName] = useState<string | undefined>(undefined);
  const lastTrackedRoute = useRef<string | undefined>(undefined);
  const updateCurrentRoute = () => {
    const name = navigationRef.getCurrentRoute()?.name;
    setCurrentRouteName(name);
    // Screen NAME only (never params, which carry league ids).
    // Redirect-only legacy routes are not real views; the destination is tracked.
    if (name && name !== lastTrackedRoute.current && !isLegacyRedirectRoute(name)) {
      lastTrackedRoute.current = name;
      // The fictional sample league is never tracked (no analytics pollution).
      if (name !== 'SampleLeague') trackScreen(name);
    }
  };

  const signedIn = Boolean(session);
  useEffect(() => {
    if (!signedIn) return;
    const task = InteractionManager.runAfterInteractions(() => {
      preloadInSequence(TOP_SCREEN_LOADERS, (run) => setTimeout(run, PRELOAD_GAP_MS));
    });
    return () => task.cancel();
  }, [signedIn]);

  const navigationTheme: Theme = {
    ...(isDark ? DarkTheme : DefaultTheme),
    colors: {
      ...(isDark ? DarkTheme.colors : DefaultTheme.colors),
      primary: colors.accent,
      // Transparent so the root AppBackground shows through every screen.
      background: 'transparent',
      card: 'transparent',
      text: colors.textPrimary,
      border: colors.hairline,
      notification: colors.danger,
    },
  };

  // While signed in, also hold on LoadingScreen until the onboarding flag
  // has been read from storage (see OnboardingContext) — otherwise the very
  // first frame after sign-in would briefly assume "not completed" and
  // flash the tutorial before the AsyncStorage read resolves.
  if (loading || (session && onboardingComplete === null)) {
    return (
      <LoadingScreen />
    );
  }

  // Drives the AppStack's initial screen only (see below) — a returning
  // user with the flag already true is unaffected even while this is
  // computed on every render.
  const showOnboardingFirst = Boolean(session) && onboardingComplete === false;
  // The whole first-run flow (carousel + its trial-offer Paywall step) hides
  // the orb, not just the Onboarding route itself.
  const hideFloatingChrome = currentRouteName === 'Onboarding' || showOnboardingFirst;

  return (
    <PlayerQuickViewProvider>
    <View style={{ flex: 1, backgroundColor: colors.background }}>
    {/* The single shared animated page background, behind every screen. */}
    <AppBackground />
    <NavigationContainer
      ref={navigationRef}
      theme={navigationTheme}
      onReady={updateCurrentRoute}
      onStateChange={updateCurrentRoute}
    >
      {session ? (
        <View style={{ flex: 1 }}>
        <AppStack.Navigator
          // Remounts the stack (with a fresh initialRouteName) the moment
          // onboardingComplete flips from false to true, so completing/
          // skipping the tutorial lands on Home without any manual
          // navigation.reset call from OnboardingScreen itself.
          key={showOnboardingFirst ? 'onboarding-first' : 'app'}
          initialRouteName={showOnboardingFirst ? 'Onboarding' : 'Home'}
          screenOptions={{
            // Default iOS behavior shows the previous screen's title next to
            // the back chevron — on a league-scoped stack that repeats the
            // league name as a redundant "pill" on every screen. "minimal"
            // keeps just the chevron.
            headerBackButtonDisplayMode: 'minimal',
            // Transparent (not a flat colors.background fill) so each
            // screen's own GridBackground gradient wash extends up behind
            // the header instead of stopping at a hard seam where the
            // header used to sit — coridian_'s "the background gradient
            // should start in the header and bleed into the main
            // background." Every screen must add its own top padding sized
            // to the (now-floating) header's height, via useHeaderHeight(),
            // since a transparent header no longer reserves layout space.
            headerTransparent: true,
            headerStyle: { backgroundColor: 'transparent' },
            // Blurred/opaque backdrop so scrolling content never shows
            // through the title and header chips (see HeaderBackdrop).
            headerBackground: () => <HeaderBackdrop />,
            headerTintColor: colors.textPrimary,
            headerShadowVisible: false,
            headerTitleAlign: 'center',
            // Transparent: the shared animated AppBackground sits behind the
            // whole navigator. 'fade' because a sliding transparent screen
            // would show the previous screen through itself mid-transition.
            contentStyle: { backgroundColor: 'transparent' },
            animation: 'fade',
          }}
        >
          <AppStack.Screen
            name="Onboarding"
            component={OnboardingScreen}
            options={{ headerShown: false, gestureEnabled: false }}
          />
          <AppStack.Screen
            name="Home"
            component={HomeScreen}
            options={({ navigation }) => ({
              headerTitle: () => (
                <BrandMark width={48} />
              ),
              headerRight: () => (
                <View style={{ flexDirection: 'row', gap: 16 }}>
                  <TouchableOpacity onPress={() => navigation.navigate('News')} hitSlop={8} accessibilityRole="button" accessibilityLabel="News">
                    <Ionicons name="globe-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => navigation.navigate('More')} hitSlop={8} accessibilityRole="button" accessibilityLabel="Account">
                    <Ionicons name="ellipsis-horizontal-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>
              ),
            })}
          />
          <AppStack.Screen name="LeagueDetail" component={LeagueDetailRedirect} />
          <AppStack.Screen name="TeamRoster" component={TeamRosterScreen} />
          <AppStack.Screen name="News" component={NewsScreen} options={{ title: 'News' }} />
          <AppStack.Screen name="More" component={MoreScreen} options={{ title: 'Account' }} />
          <AppStack.Screen name="Design" component={DesignScreen} options={{ title: 'Design' }} />
          <AppStack.Screen name="SampleLeague" component={SampleLeagueScreen} options={{ title: 'Sample league' }} />
          <AppStack.Screen name="LegalPage" component={LegalPageScreen} />
          <AppStack.Screen
            name="HowWeEvaluate"
            component={HowWeEvaluateScreen}
            options={{ title: 'How We Evaluate' }}
          />
          <AppStack.Screen name="Players" component={PlayersScreen} />
          <AppStack.Screen name="PlayerDetail" component={PlayerDetailScreen} />
          <AppStack.Screen name="PlayerCompare" component={PlayerCompareScreen} />
          <AppStack.Screen name="Waivers" component={EspnWaiversScreen} />
          <AppStack.Screen name="Recap" component={EspnRecapScreen} />
          <AppStack.Screen name="Dashboard" component={EspnDashboardScreen} />
          <AppStack.Screen name="Trades" component={TradesScreen} />
          <AppStack.Screen name="TradeOffer" component={TradeOfferScreen} />
          <AppStack.Screen name="Teams" component={TeamsScreen} />
          <AppStack.Screen name="PlayoffOdds" component={PlayoffOddsRedirect} />
          <AppStack.Screen name="Games" component={EspnGamesScreen} />
          <AppStack.Screen name="Commissioner" component={EspnCommissionerScreen} />
          <AppStack.Screen name="DraftCenter" component={EspnDraftCenterScreen} />
          <AppStack.Screen name="FantasySim" component={EspnFantasySimScreen} />
          <AppStack.Screen name="PickDetail" component={EspnPickDetailScreen} />
          <AppStack.Screen name="MyTeam" component={MyTeamScreen} />
          <AppStack.Screen name="Matchup" component={EspnMatchupScreen} />
          <AppStack.Screen name="Alerts" component={EspnAlertsScreen} />
          <AppStack.Screen name="GmTargets" component={GmTargetsRedirect} />
          <AppStack.Screen name="CollegeProspects" component={CollegeProspectsScreen} />
          <AppStack.Screen name="CollegeProspectDetail" component={ProspectScoutingDetailScreen} />
          <AppStack.Screen name="TeamStance" component={TeamStanceRedirect} />
          <AppStack.Screen name="GmPlan" component={EspnGmPlanScreen} />
          <AppStack.Screen name="TradeHistory" component={TradeHistoryScreen} options={{ title: 'Trade History' }} />
          <AppStack.Screen name="Community" component={CommunityScreen} options={{ title: 'Community' }} />
          <AppStack.Screen name="Features" component={FeaturesScreen} options={{ title: 'What FantasyDesk can do' }} />
          <AppStack.Screen name="Portfolio" component={PortfolioScreen} options={{ title: 'Portfolio' }} />
          <AppStack.Screen name="GmGame" component={GmGameScreen} options={{ title: 'Fantasy Sim' }} />
          <AppStack.Screen name="FounderAnalytics" component={FounderAnalyticsScreen} options={{ title: 'Founder Analytics' }} />
          <AppStack.Screen name="LiveDraft" component={EspnLiveDraftScreen} />
          <AppStack.Screen name="GuessThePlayerLeaderboard" component={EspnGuessLeaderboardScreen} />
          <AppStack.Screen
            name="Paywall"
            component={PaywallScreen}
            options={{ presentation: 'modal', title: 'Pro', animation: 'default', contentStyle: { backgroundColor: colors.background } }}
          />
          <AppStack.Screen
            name="TrialLapsed"
            component={TrialLapsedScreen}
            options={{ presentation: 'modal', headerShown: false, animation: 'default', contentStyle: { backgroundColor: colors.background } }}
          />
        </AppStack.Navigator>
        {hideFloatingChrome ? null : <GmOrb />}
        {hideFloatingChrome ? null : <TradeOutcomePrompt />}
        {hideFloatingChrome ? null : <GuessThePlayerPrompt />}
        {hideFloatingChrome ? null : <GuessThePlayerNameMatchPrompt />}
        </View>
      ) : (
        <AuthStack.Navigator screenOptions={{ headerShown: false, contentStyle: { backgroundColor: 'transparent' } }}>
          <AuthStack.Screen name="Login" component={LoginScreen} />
        </AuthStack.Navigator>
      )}
    </NavigationContainer>
    </View>
    </PlayerQuickViewProvider>
  );
}
