import React, { useState } from 'react';
import { Image, TouchableOpacity, View } from 'react-native';
import { DarkTheme, DefaultTheme, NavigationContainer, type Theme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import type { DraftPickAsset, RankedPlayer } from '../lib/api';
import GmOrb from '../components/GmOrb';
import TradeOutcomePrompt from '../components/TradeOutcomePrompt';
import { navigationRef } from './navigationRef';

import { useAuth } from '../context/AuthContext';
import { useOnboarding } from '../context/OnboardingContext';
import { useThemeMode } from '../context/ThemeModeContext';
import LoginScreen from '../screens/LoginScreen';
import OnboardingScreen from '../screens/OnboardingScreen';
import HomeScreen from '../screens/HomeScreen';
import LeagueDetailScreen from '../screens/LeagueDetailScreen';
import TeamRosterScreen from '../screens/TeamRosterScreen';
import PaywallScreen from '../screens/PaywallScreen';
import TradeCalculatorScreen from '../screens/TradeCalculatorScreen';
import NewsScreen from '../screens/NewsScreen';
import MoreScreen from '../screens/MoreScreen';
import LegalPageScreen from '../screens/LegalPageScreen';
import HowWeEvaluateScreen from '../screens/HowWeEvaluateScreen';
import PlayersScreen from '../screens/PlayersScreen';
import PlayerDetailScreen from '../screens/PlayerDetailScreen';
import PlayerCompareScreen from '../screens/PlayerCompareScreen';
import WaiversScreen from '../screens/WaiversScreen';
import TradeAnalyzerScreen from '../screens/TradeAnalyzerScreen';
import RecapScreen from '../screens/RecapScreen';
import AlertsScreen from '../screens/AlertsScreen';
import GmTargetsScreen from '../screens/GmTargetsScreen';
import TeamStanceScreen from '../screens/TeamStanceScreen';
import DashboardScreen from '../screens/DashboardScreen';
import TradeHubScreen from '../screens/TradeHubScreen';
import TradeFinderScreen from '../screens/TradeFinderScreen';
import TeamsScreen from '../screens/TeamsScreen';
import DraftCenterScreen from '../screens/DraftCenterScreen';
import PickDetailScreen from '../screens/PickDetailScreen';
import MyTeamScreen from '../screens/MyTeamScreen';
import MatchupScreen from '../screens/MatchupScreen';
import LoadingScreen from '../screens/LoadingScreen';

export type RootStackParamList = {
  Home: undefined;
  Onboarding: undefined;
  LeagueDetail: { leagueId: string; leagueName: string };
  TeamRoster: { ownerName: string; playerIds: string[]; leagueId: string; leagueName: string; rosterId: string };
  Paywall: undefined;
  TradeCalculator: { leagueId: string; leagueName: string };
  News: undefined;
  More: undefined;
  LegalPage: { pageKey: string };
  HowWeEvaluate: undefined;
  Players: { leagueId: string; leagueName: string };
  PlayerDetail: { player: RankedPlayer; leagueId: string; leagueName: string };
  PlayerCompare: { player: RankedPlayer; leagueId: string; leagueName: string };
  GmTargets: { leagueId: string; leagueName: string };
  TeamStance: { leagueId: string; leagueName: string };
  Waivers: { leagueId: string; leagueName: string };
  TradeAnalyzer: { leagueId: string; leagueName: string };
  Recap: { leagueId: string; leagueName: string };
  Dashboard: { leagueId: string; leagueName: string };
  TradeHub: { leagueId: string; leagueName: string };
  TradeFinder: { leagueId: string; leagueName: string };
  Teams: { leagueId: string; leagueName: string };
  DraftCenter: { leagueId: string; leagueName: string };
  PickDetail: { pick: DraftPickAsset; leagueId: string; leagueName: string };
  MyTeam: { leagueId: string; leagueName: string };
  Matchup: { leagueId: string; leagueName: string };
  Alerts: { leagueId: string; leagueName: string };
};

const AppStack = createNativeStackNavigator<RootStackParamList>();
const AuthStack = createNativeStackNavigator();

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
  const updateCurrentRoute = () => setCurrentRouteName(navigationRef.getCurrentRoute()?.name);

  const navigationTheme: Theme = {
    ...(isDark ? DarkTheme : DefaultTheme),
    colors: {
      ...(isDark ? DarkTheme.colors : DefaultTheme.colors),
      primary: colors.accent,
      background: colors.background,
      card: colors.background,
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
  const hideFloatingChrome = currentRouteName === 'Onboarding';

  return (
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
            headerTintColor: colors.textPrimary,
            headerShadowVisible: false,
            headerTitleAlign: 'center',
            contentStyle: { backgroundColor: colors.background },
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
                <Image source={require('../../assets/icon.png')} style={{ width: 28, height: 28, borderRadius: 8 }} />
              ),
              headerRight: () => (
                <View style={{ flexDirection: 'row', gap: 16 }}>
                  <TouchableOpacity onPress={() => navigation.navigate('News')} hitSlop={8}>
                    <Ionicons name="globe-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => navigation.navigate('More')} hitSlop={8}>
                    <Ionicons name="ellipsis-horizontal-outline" size={22} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>
              ),
            })}
          />
          <AppStack.Screen name="LeagueDetail" component={LeagueDetailScreen} />
          <AppStack.Screen name="TeamRoster" component={TeamRosterScreen} />
          <AppStack.Screen
            name="TradeCalculator"
            component={TradeCalculatorScreen}
            options={{ title: 'Trade Calculator' }}
          />
          <AppStack.Screen name="News" component={NewsScreen} options={{ title: 'News' }} />
          <AppStack.Screen name="More" component={MoreScreen} options={{ title: 'More' }} />
          <AppStack.Screen name="LegalPage" component={LegalPageScreen} />
          <AppStack.Screen
            name="HowWeEvaluate"
            component={HowWeEvaluateScreen}
            options={{ title: 'How We Evaluate' }}
          />
          <AppStack.Screen name="Players" component={PlayersScreen} />
          <AppStack.Screen name="PlayerDetail" component={PlayerDetailScreen} />
          <AppStack.Screen name="PlayerCompare" component={PlayerCompareScreen} />
          <AppStack.Screen name="Waivers" component={WaiversScreen} />
          <AppStack.Screen name="TradeAnalyzer" component={TradeAnalyzerScreen} />
          <AppStack.Screen name="Recap" component={RecapScreen} />
          <AppStack.Screen name="Dashboard" component={DashboardScreen} />
          <AppStack.Screen name="TradeHub" component={TradeHubScreen} />
          <AppStack.Screen name="TradeFinder" component={TradeFinderScreen} />
          <AppStack.Screen name="Teams" component={TeamsScreen} />
          <AppStack.Screen name="DraftCenter" component={DraftCenterScreen} />
          <AppStack.Screen name="PickDetail" component={PickDetailScreen} />
          <AppStack.Screen name="MyTeam" component={MyTeamScreen} />
          <AppStack.Screen name="Matchup" component={MatchupScreen} />
          <AppStack.Screen name="Alerts" component={AlertsScreen} />
          <AppStack.Screen name="GmTargets" component={GmTargetsScreen} />
          <AppStack.Screen name="TeamStance" component={TeamStanceScreen} />
          <AppStack.Screen
            name="Paywall"
            component={PaywallScreen}
            options={{ presentation: 'modal', title: 'Premium' }}
          />
        </AppStack.Navigator>
        {hideFloatingChrome ? null : <GmOrb />}
        {hideFloatingChrome ? null : <TradeOutcomePrompt />}
        </View>
      ) : (
        <AuthStack.Navigator screenOptions={{ headerShown: false }}>
          <AuthStack.Screen name="Login" component={LoginScreen} />
        </AuthStack.Navigator>
      )}
    </NavigationContainer>
  );
}
