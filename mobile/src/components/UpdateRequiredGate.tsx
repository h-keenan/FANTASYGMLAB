import React, { useEffect, useState } from 'react';
import { Linking, Platform } from 'react-native';
import Constants from 'expo-constants';

import { fetchGate, type GateDecision } from '../lib/appVersionGate';
import { env } from '../lib/env';
import StandaloneNoticeScreen from './StandaloneNoticeScreen';

/**
 * Checks the server-provided minimum app version once on launch. Renders the
 * app immediately (fail open) and swaps to a blocking "Update required"
 * screen only if the server says this build is below the floor.
 */
export default function UpdateRequiredGate({ children }: { children: React.ReactNode }) {
  const [gate, setGate] = useState<GateDecision>({ updateRequired: false, storeUrl: '' });

  useEffect(() => {
    let cancelled = false;
    void fetchGate({
      apiBaseUrl: env.apiBaseUrl,
      platform: Platform.OS,
      currentVersion: Constants.expoConfig?.version ?? '',
    }).then((decision) => {
      if (!cancelled) setGate(decision);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (gate.updateRequired) {
    return (
      <StandaloneNoticeScreen
        title="Update required"
        body="This version of FantasyDesk is no longer supported. Update to the latest version to keep using the app."
        actionLabel="Update now"
        onAction={() => {
          if (gate.storeUrl) void Linking.openURL(gate.storeUrl).catch(() => undefined);
        }}
      />
    );
  }
  return <>{children}</>;
}
