import React, { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import { SkeletonPage } from '../components/Skeleton';
import CollegeScoutingPanel from '../components/CollegeScoutingPanel';
import GridBackground from '../components/GridBackground';
import { getLastLeague } from '../lib/lastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { PAGE_TOP_GAP, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'CollegeProspects'>;

/**
 * College Scouting is now the Prospects tab of Players. This route stays
 * for older links and the Dashboard interest prompt: with a last-opened
 * league it forwards to that tab; with no league it renders the
 * league-independent board here, so scouting never requires picking a league.
 */
export default function CollegeProspectsScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const styles = useMemo(() => createStyles(), []);
  const [resolved, setResolved] = useState(false);

  useScreenHeaderTitle(navigation, 'Prospects');

  useEffect(() => {
    let cancelled = false;
    void getLastLeague().then((last) => {
      if (cancelled) return;
      if (last) {
        navigation.replace('Players', { leagueId: last.leagueId, leagueName: last.leagueName, tab: 'prospects' });
      } else {
        setResolved(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [navigation]);

  if (!resolved) return <SkeletonPage label="Prospects" layout="list" topInset={headerHeight} />;

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <CollegeScoutingPanel onOpenProspect={(prospect) => navigation.navigate('CollegeProspectDetail', { prospect })} />
      </ScrollView>
    </View>
  );
}

function createStyles() {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: 'transparent' },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
    content: { paddingHorizontal: spacing.lg, paddingTop: PAGE_TOP_GAP },
  });
}
