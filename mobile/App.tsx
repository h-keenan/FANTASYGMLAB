import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from './src/context/AuthContext';
import { DensityProvider } from './src/context/DensityContext';
import RootNavigator from './src/navigation/RootNavigator';
import { configureRevenueCat } from './src/lib/revenuecat';
import { initAds } from './src/lib/ads';

export default function App() {
  useEffect(() => {
    configureRevenueCat();
    void initAds();
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <DensityProvider>
          <AuthProvider>
            <RootNavigator />
          </AuthProvider>
        </DensityProvider>
        <StatusBar style="light" />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
