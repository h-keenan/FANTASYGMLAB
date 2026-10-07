import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import BrandHeaderBar from '../components/BrandHeaderBar';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TradeAnalyzerScreen from './TradeAnalyzerScreen';
import TradeFinderScreen from './TradeFinderScreen';
import TradeHubScreen from './TradeHubScreen';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Trades'>;
type TradesTab = 'block' | 'search' | 'make';

const TAB_OPTIONS: Array<{ key: TradesTab; label: string }> = [
  { key: 'block', label: 'Trade Block' },
  { key: 'search', label: 'Search' },
  { key: 'make', label: 'Make a Trade' },
];

/**
 * Single host screen for FantasyGM Lab's three trade workflows — Trade Hub
 * ("Trade Block"), Trade Finder ("Search"), and Trade Analyzer ("Make a
 * Trade") — consolidated behind one Madden-style trade menu per coridian_'s
 * request, replacing three standalone screens that each duplicated the same
 * header chrome (League Switcher / Evaluation Lens / GM Stance / Trade
 * History buttons, BrandHeaderBar). This screen owns that header exactly
 * once; the three screens below are otherwise unchanged — same state,
 * same API calls, same rendering — only how they receive
 * leagueId/leagueName/navigation (props instead of route params) and who
 * sets the header (this screen, not them) changed. Trade Calculator is a
 * separate, not-yet-folded-in screen (PR 2) and isn't part of this host.
 *
 * Each tab is lazy-mounted on first visit and then kept mounted (see
 * `visitedTabs`), so opening Trades doesn't fire all three screens' network
 * calls up front, but switching tabs back and forth doesn't re-fetch either.
 */
export default function TradesScreen({ route, navigation }: Props) {
  const { leagueId, leagueName, initialTab } = route.params;
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  const [activeTab, setActiveTab] = useState<TradesTab>(initialTab ?? 'block');
  const [visitedTabs, setVisitedTabs] = useState<Set<TradesTab>>(
    () => new Set<TradesTab>([initialTab ?? 'block']),
  );

  const onChangeTab = useCallback((tab: TradesTab) => {
    setActiveTab(tab);
    setVisitedTabs((prev) => (prev.has(tab) ? prev : new Set(prev).add(tab)));
  }, []);

  useScreenHeaderTitle(navigation, 'Trades', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
          {/* Same Trade History affordance Trade Hub used to carry on its own
              header (discoverability audit, 2026-09-26) — now lives on the
              shared Trades header instead of just one of the three tabs. */}
          <TouchableOpacity
            onPress={() => navigation.navigate('TradeHistory')}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel="Trade History"
            accessibilityHint="Trades you've confirmed and how they've worked out"
          >
            <Ionicons name="time-outline" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      ),
    });
  }, [navigation, leagueId, leagueName, colors.textSecondary]);

  return (
    <View style={styles.root}>
      <View style={[styles.topSection, { paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <View style={styles.tabBarWrap}>
          <SegmentedTabBar<TradesTab> options={TAB_OPTIONS} active={activeTab} onChange={onChangeTab} />
        </View>
      </View>
      <View style={styles.contentArea}>
        {visitedTabs.has('block') ? (
          <View style={[styles.tabPane, activeTab !== 'block' && styles.tabPaneHidden]}>
            <TradeHubScreen leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
          </View>
        ) : null}
        {visitedTabs.has('search') ? (
          <View style={[styles.tabPane, activeTab !== 'search' && styles.tabPaneHidden]}>
            <TradeFinderScreen leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
          </View>
        ) : null}
        {visitedTabs.has('make') ? (
          <View style={[styles.tabPane, activeTab !== 'make' && styles.tabPaneHidden]}>
            <TradeAnalyzerScreen leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
          </View>
        ) : null}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    root: { flex: 1, backgroundColor: colors.background },
    topSection: { backgroundColor: colors.background },
    tabBarWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs, paddingBottom: spacing.sm },
    contentArea: { flex: 1 },
    tabPane: { flex: 1 },
    // display: 'none' (not unmounting) is what keeps each tab's state/scroll
    // position/in-flight requests alive across switches — see the lazy-mount
    // note above.
    tabPaneHidden: { display: 'none' },
  });
}
