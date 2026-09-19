import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from './src/context/AuthContext';
import { DensityProvider } from './src/context/DensityContext';
import { GmStanceProvider } from './src/context/GmStanceContext';
import { ShowcaseModeProvider } from './src/context/ShowcaseModeContext';
import RootNavigator from './src/navigation/RootNavigator';
import { configureRevenueCat } from './src/lib/revenuecat';
import { initAds } from './src/lib/ads';
import { registerNotificationTapHandler } from './src/lib/pushNotifications';

export default function App() {
  useEffect(() => {
    configureRevenueCat();
    void initAds();
    return registerNotificationTapHandler();
  }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <DensityProvider>
          <GmStanceProvider>
            {/* Outside AuthProvider so the masking flag is armed from
                storage before the first authorized request goes out. */}
            <ShowcaseModeProvider>
              <AuthProvider>
                <RootNavigator />
              </AuthProvider>
            </ShowcaseModeProvider>
          </GmStanceProvider>
        </DensityProvider>
        <StatusBar style="light" />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
