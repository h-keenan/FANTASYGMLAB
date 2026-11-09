import React, { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import BrandedSpinner from '../components/BrandedSpinner';
import CollegeScoutingPanel from '../components/CollegeScoutingPanel';
import GridBackground from '../components/GridBackground';
import { getLastLeague } from '../lib/lastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'CollegeProspects'>;

/**
 * College Scouting now lives in Draft Center's Scouting tab. This route stays
 * for older links, the Dashboard interest prompt and More: with a last-opened
 * league it forwards to that tab; with no league it renders the
 * league-independent board here, so scouting never requires picking a league.
 */
export default function CollegeProspectsScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const styles = useMemo(() => createStyles(), []);
  const [resolved, setResolved] = useState(false);

  useScreenHeaderTitle(navigation, 'College Scouting');

  useEffect(() => {
    let cancelled = false;
    void getLastLeague().then((last) => {
      if (cancelled) return;
      if (last) {
        navigation.replace('DraftCenter', { leagueId: last.leagueId, leagueName: last.leagueName, tab: 'scouting' });
      } else {
        setResolved(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [navigation]);

  if (!resolved) return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;

  return (
    <View style={styles.container}>
      <GridBackground />
      <ScrollView contentContainerStyle={[styles.content, { paddingTop: headerHeight, paddingBottom: orbClearance }]}>
        <BrandHeaderBar />
        <CollegeScoutingPanel onOpenProspect={(prospect) => navigation.navigate('CollegeProspectDetail', { prospect })} />
      </ScrollView>
    </View>
  );
}

function createStyles() {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: 'transparent' },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
    content: { paddingHorizontal: spacing.lg },
  });
}
