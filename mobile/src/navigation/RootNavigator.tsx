import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { useAuth } from '../context/AuthContext';
import LoginScreen from '../screens/LoginScreen';
import HomeScreen from '../screens/HomeScreen';
import LeagueDetailScreen from '../screens/LeagueDetailScreen';
import TeamRosterScreen from '../screens/TeamRosterScreen';
import PaywallScreen from '../screens/PaywallScreen';

export type RootStackParamList = {
  Home: undefined;
  LeagueDetail: { leagueId: string; leagueName: string };
  TeamRoster: { ownerName: string; playerIds: string[] };
  Paywall: undefined;
};

const AppStack = createNativeStackNavigator<RootStackParamList>();
const AuthStack = createNativeStackNavigator();

export default function RootNavigator() {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {session ? (
        <AppStack.Navigator>
          <AppStack.Screen
            name="Home"
            component={HomeScreen}
            options={{ title: 'FantasyGM Lab' }}
          />
          <AppStack.Screen name="LeagueDetail" component={LeagueDetailScreen} />
          <AppStack.Screen name="TeamRoster" component={TeamRosterScreen} />
          <AppStack.Screen
            name="Paywall"
            component={PaywallScreen}
            options={{ presentation: 'modal', title: 'Premium' }}
          />
        </AppStack.Navigator>
      ) : (
        <AuthStack.Navigator screenOptions={{ headerShown: false }}>
          <AuthStack.Screen name="Login" component={LoginScreen} />
        </AuthStack.Navigator>
      )}
    </NavigationContainer>
  );
}
