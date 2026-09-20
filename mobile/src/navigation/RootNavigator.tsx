import React from 'react';
import { Image, TouchableOpacity, View } from 'react-native';
import { DarkTheme, NavigationContainer, type Theme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { colors } from '../theme';
import type { DraftPickAsset, RankedPlayer } from '../lib/api';
import GmOrb from '../components/GmOrb';
import TradeOutcomePrompt from '../components/TradeOutcomePrompt';
import { navigationRef } from './navigationRef';

import { useAuth } from '../context/AuthContext';
import LoginScreen from '../screens/LoginScreen';
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
import DashboardScreen from '../screens/DashboardScreen';
import TradeHubScreen from '../screens/TradeHubScreen';
import TeamsScreen from '../screens/TeamsScreen';
import DraftCenterScreen from '../screens/DraftCenterScreen';
import PickDetailScreen from '../screens/PickDetailScreen';
import MyTeamScreen from '../screens/MyTeamScreen';
import MatchupScreen from '../screens/MatchupScreen';
import LoadingScreen from '../screens/LoadingScreen';

export type RootStackParamList = {
  Home: undefined;
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
  Waivers: { leagueId: string; leagueName: string };
  TradeAnalyzer: { leagueId: string; leagueName: string };
  Recap: { leagueId: string; leagueName: string };
  Dashboard: { leagueId: string; leagueName: string };
  TradeHub: { leagueId: string; leagueName: string };
  Teams: { leagueId: string; leagueName: string };
  DraftCenter: { leagueId: string; leagueName: string };
  PickDetail: { pick: DraftPickAsset; leagueId: string; leagueName: string };
  MyTeam: { leagueId: string; leagueName: string };
  Matchup: { leagueId: string; leagueName: string };
  Alerts: { leagueId: string; leagueName: string };
};

const AppStack = createNativeStackNavigator<RootStackParamList>();
const AuthStack = createNativeStackNavigator();

const navigationTheme: Theme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: colors.accent,
    background: colors.background,
    card: colors.background,
    text: colors.textPrimary,
    border: colors.hairline,
    notification: colors.danger,
  },
};

export default function RootNavigator() {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <LoadingScreen />
    );
  }

  return (
    <NavigationContainer ref={navigationRef} theme={navigationTheme}>
      {session ? (
        <View style={{ flex: 1 }}>
        <AppStack.Navigator
          screenOptions={{
            // Default iOS behavior shows the previous screen's title next to
            // the back chevron — on a league-scoped stack that repeats the
            // league name as a redundant "pill" on every screen. "minimal"
            // keeps just the chevron.
            headerBackButtonDisplayMode: 'minimal',
            headerStyle: { backgroundColor: colors.background },
            headerTintColor: colors.textPrimary,
            headerShadowVisible: true,
            headerTitleAlign: 'center',
            contentStyle: { backgroundColor: colors.background },
          }}
        >
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
          <AppStack.Screen name="Teams" component={TeamsScreen} />
          <AppStack.Screen name="DraftCenter" component={DraftCenterScreen} />
          <AppStack.Screen name="PickDetail" component={PickDetailScreen} />
          <AppStack.Screen name="MyTeam" component={MyTeamScreen} />
          <AppStack.Screen name="Matchup" component={MatchupScreen} />
          <AppStack.Screen name="Alerts" component={AlertsScreen} />
          <AppStack.Screen name="GmTargets" component={GmTargetsScreen} />
          <AppStack.Screen
            name="Paywall"
            component={PaywallScreen}
            options={{ presentation: 'modal', title: 'Premium' }}
          />
        </AppStack.Navigator>
        <GmOrb />
        <TradeOutcomePrompt />
        </View>
      ) : (
        <AuthStack.Navigator screenOptions={{ headerShown: false }}>
          <AuthStack.Screen name="Login" component={LoginScreen} />
        </AuthStack.Navigator>
      )}
    </NavigationContainer>
  );
}
