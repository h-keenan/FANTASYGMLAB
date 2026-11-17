import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { staleNote } from '../lib/badDayCopy';
import { isOffline, subscribeConnectivity } from '../lib/connectivity';
import { spacing, type ThemeColors } from '../theme';

/**
 * The one "as of" note under content painted from the React Query cache. Quiet when the data is fresh; when the device is
 * offline, the last refresh failed (`refreshFailed`) or the data is over 10 minutes old it says when it was last current
 * ("As of 3:42 PM"). Pass the query's `dataUpdatedAt`. Web has no persisted query cache yet (see the bad-day audit).
 */
export default function StaleNote({ updatedAt, refreshFailed = false }: { updatedAt: number; refreshFailed?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [offline, setOffline] = useState(isOffline());
  useEffect(() => subscribeConnectivity(setOffline), []);
  const note = staleNote(updatedAt, { offline: offline || refreshFailed });
  if (!note) return null;
  return (
    <AppText style={styles.note} testID="stale-note" accessibilityLiveRegion="polite">
      {note}
    </AppText>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    note: { fontSize: 12.5, color: colors.textTertiary, marginBottom: spacing.xs },
  });
}
