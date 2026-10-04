import React, { useCallback, useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
  Inter_800ExtraBold,
  useFonts,
} from '@expo-google-fonts/inter';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';

import { AuthProvider } from './src/context/AuthContext';
import { CollegeInterestProvider } from './src/context/CollegeInterestContext';
import { DensityProvider } from './src/context/DensityContext';
import { GmStanceProvider } from './src/context/GmStanceContext';
import { OnboardingProvider } from './src/context/OnboardingContext';
import { ValuationLensProvider } from './src/context/ValuationLensContext';
import { ShowcaseModeProvider } from './src/context/ShowcaseModeContext';
import { ThemeModeProvider, useThemeMode } from './src/context/ThemeModeContext';
import RootNavigator from './src/navigation/RootNavigator';
import { configureRevenueCat } from './src/lib/revenuecat';
import { initAds } from './src/lib/ads';
import { registerNotificationTapHandler } from './src/lib/pushNotifications';
import { asyncStoragePersister, PERSIST_MAX_AGE_MS, queryClient } from './src/lib/queryClient';

// Holds the native splash up past its default auto-hide — AppText (every
// screen's Text) needs these weight files registered with the native font
// manager before first paint, or the very first frame renders in the OS
// fallback font and visibly reflows into Inter a moment later.
void SplashScreen.preventAutoHideAsync();

export default function App() {
  const [fontsLoaded] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    Inter_800ExtraBold,
  });

  const onLayoutRootView = useCallback(async () => {
    if (fontsLoaded) {
      await SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  useEffect(() => {
    configureRevenueCat();
    void initAds();
    return registerNotificationTapHandler();
  }, []);

  if (!fontsLoaded) {
    return null;
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }} onLayout={onLayoutRootView}>
      {/* Wraps everything else so any screen can adopt `useQuery` for the
          shared "show cached data instantly, refresh in background"
          behavior — see src/lib/queryClient.ts. The persister restores
          last session's cache from AsyncStorage before screens mount,
          which is what lets a cold app start paint from cache too, not
          just in-memory nav between screens. */}
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{ persister: asyncStoragePersister, maxAge: PERSIST_MAX_AGE_MS }}
      >
        <SafeAreaProvider>
          <ThemeModeProvider>
            <DensityProvider>
              <GmStanceProvider>
                <ValuationLensProvider>
                  {/* Outside AuthProvider so the masking flag is armed from
                      storage before the first authorized request goes out. */}
                  <ShowcaseModeProvider>
                    <OnboardingProvider>
                      <CollegeInterestProvider>
                        <AuthProvider>
                          <RootNavigator />
                        </AuthProvider>
                      </CollegeInterestProvider>
                    </OnboardingProvider>
                  </ShowcaseModeProvider>
                </ValuationLensProvider>
              </GmStanceProvider>
            </DensityProvider>
            <ThemedStatusBar />
          </ThemeModeProvider>
        </SafeAreaProvider>
      </PersistQueryClientProvider>
    </GestureHandlerRootView>
  );
}

/** Light-mode needs dark status bar icons on its icy-white background —
 * the old hardcoded `style="light"` only ever made sense for the
 * dark-only theme this app had before today. */
function ThemedStatusBar() {
  const { isDark } = useThemeMode();
  return <StatusBar style={isDark ? 'light' : 'dark'} />;
}
