import React from 'react';
import { StyleSheet, View } from 'react-native';
import { StackActions } from '@react-navigation/native';
import { useHeaderHeight } from '@react-navigation/elements';

import EmptyState from './EmptyState';
import GridBackground from './GridBackground';
import { navigationRef } from '../navigation/navigationRef';
import { importedPlatformLabel, notAvailableMessage } from '../lib/leaguePlatform';
import { useThemeMode } from '../context/ThemeModeContext';

/**
 * Shown in place of a league screen an ESPN league can't feed yet (see
 * lib/leaguePlatform.ts). Says so plainly and points at the screens that
 * do work, instead of loading a Sleeper-only screen that would error or
 * show empty data. Rendered by RootNavigator's withEspnGate, so no
 * individual screen carries its own copy of this check.
 */
export default function EspnUnavailableScreen({
  leagueId,
  leagueName,
}: {
  leagueId: string;
  leagueName: string;
}) {
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const params = { leagueId, leagueName };
  return (
    <View style={[styles.root, { paddingTop: headerHeight, backgroundColor: colors.background }]}>
      <GridBackground />
      <EmptyState
        icon="construct-outline"
        title={notAvailableMessage(leagueId)}
        subtitle={`${leagueName} is ${importedPlatformLabel(leagueId) === 'ESPN' ? 'an' : 'a'} ${importedPlatformLabel(leagueId) || 'ESPN'} league. This screen needs league data FantasyDesk can only read from Sleeper so far. Dashboard, Matchup, My Team, Trade Analyzer, Players and League Rankings work for it now.`}
        actionLabel="Open Dashboard"
        onPressAction={() => navigationRef.dispatch(StackActions.replace('Dashboard', params))}
        secondaryLabel="Open Trade Analyzer"
        onPressSecondary={() =>
          navigationRef.dispatch(StackActions.replace('Trades', { ...params, initialTab: 'make' }))
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'center' },
});
