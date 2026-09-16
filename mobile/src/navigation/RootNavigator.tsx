import React from 'react';
import { ActivityIndicator, Text, TouchableOpacity, View } from 'react-native';
import { DarkTheme, NavigationContainer, type Theme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { colors } from '../theme';
import type { RankedPlayer } from '../lib/api';
import GmOrb from '../components/GmOrb';
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
import PlayersScreen from '../screens/PlayersScreen';
import PlayerDetailScreen from '../screens/PlayerDetailScreen';
import WaiversScreen from '../screens/WaiversScreen';
import TradeAnalyzerScreen from '../screens/TradeAnalyzerScreen';
import RecapScreen from '../screens/RecapScreen';
import AlertsScreen from '../screens/AlertsScreen';
import GmTargetsScreen from '../screens/GmTargetsScreen';

export type RootStackParamList = {
  Home: undefined;
  LeagueDetail: { leagueId: string; leagueName: string };
  TeamRoster: { ownerName: string; playerIds: string[] };
  Paywall: undefined;
  TradeCalculator: { leagueId: string; leagueName: string };
  News: undefined;
  More: undefined;
  LegalPage: { pageKey: string };
  Players: { leagueId: string; leagueName: string };
  PlayerDetail: { player: RankedPlayer; leagueId: string; leagueName: string };
  GmTargets: { leagueId: string; leagueName: string };
  Waivers: { leagueId: string; leagueName: string };
  TradeAnalyzer: { leagueId: string; leagueName: string };
  Recap: { leagueId: string; leagueName: string };
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
    card: colors.backgroundElevated,
    text: colors.textPrimary,
    border: colors.border,
    notification: colors.danger,
  },
};

export default function RootNavigator() {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  return (
    <NavigationContainer ref={navigationRef} theme={navigationTheme}>
      {session ? (
        <View style={{ flex: 1 }}>
        <AppStack.Navigator>
          <AppStack.Screen
            name="Home"
            component={HomeScreen}
            options={({ navigation }) => ({
              title: 'FantasyGM Lab',
              headerRight: () => (
                <View style={{ flexDirection: 'row', gap: 16 }}>
                  <TouchableOpacity onPress={() => navigation.navigate('News')} hitSlop={8}>
                    <Text style={{ color: colors.accent, fontSize: 15, fontWeight: '600' }}>News</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => navigation.navigate('More')} hitSlop={8}>
                    <Text style={{ color: colors.accent, fontSize: 15, fontWeight: '600' }}>More</Text>
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
          <AppStack.Screen name="Players" component={PlayersScreen} />
          <AppStack.Screen name="PlayerDetail" component={PlayerDetailScreen} />
          <AppStack.Screen name="Waivers" component={WaiversScreen} />
          <AppStack.Screen name="TradeAnalyzer" component={TradeAnalyzerScreen} />
          <AppStack.Screen name="Recap" component={RecapScreen} />
          <AppStack.Screen name="Alerts" component={AlertsScreen} />
          <AppStack.Screen name="GmTargets" component={GmTargetsScreen} />
          <AppStack.Screen
            name="Paywall"
            component={PaywallScreen}
            options={{ presentation: 'modal', title: 'Premium' }}
          />
        </AppStack.Navigator>
        <GmOrb />
        </View>
      ) : (
        <AuthStack.Navigator screenOptions={{ headerShown: false }}>
          <AuthStack.Screen name="Login" component={LoginScreen} />
        </AuthStack.Navigator>
      )}
    </NavigationContainer>
  );
}
