import React from 'react';
import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import Button from './Button';
import SectionHeading from './SectionHeading';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { spacing } from '../theme';

/**
 * "What to do next" button row for screens that otherwise end in a dead end
 * (Matchup, News). Mirrors web-next's components/NextSteps.tsx: keep the
 * step list and copy identical.
 */
export type NextStepKey = 'matchup' | 'waivers' | 'trade-hub' | 'trade-finder' | 'trade-analyzer' | 'my-team' | 'alerts' | 'gm-plan';

type StepRoute = 'Matchup' | 'Waivers' | 'Trades' | 'MyTeam' | 'Dashboard' | 'GmPlan';

export const NEXT_STEPS: Record<
  NextStepKey,
  { label: string; route: StepRoute; params?: { initialTab: 'block' | 'search' | 'make' } | { focus: 'alerts' } }
> = {
  matchup: { label: 'Check your lineup', route: 'Matchup' },
  waivers: { label: 'Find a waiver add', route: 'Waivers' },
  'trade-hub': { label: 'See trade ideas', route: 'Trades' },
  'trade-finder': { label: 'See other packages in Trade Finder', route: 'Trades', params: { initialTab: 'search' } },
  'trade-analyzer': { label: 'Analyze a trade', route: 'Trades', params: { initialTab: 'make' } },
  'my-team': { label: 'Review your roster', route: 'MyTeam' },
  alerts: { label: 'See news on your players', route: 'Dashboard', params: { focus: 'alerts' } },
  'gm-plan': { label: 'Open your GM Plan', route: 'GmPlan' },
};

export default function NextSteps({
  title = 'What to do next',
  steps,
  leagueId,
  leagueName,
}: {
  title?: string;
  steps: NextStepKey[];
  leagueId: string;
  leagueName: string;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  if (!leagueId) return null;
  return (
    <View style={styles.wrap} testID="next-steps">
      <SectionHeading title={title} />
      <View style={styles.row}>
        {steps.map((step) => (
          <Button
            key={step}
            variant="secondary"
            size="sm"
            label={`${NEXT_STEPS[step].label} →`}
            onPress={() => {
              const target = NEXT_STEPS[step];
              navigation.navigate(target.route as 'Matchup', { leagueId, leagueName, ...(target.params ?? {}) } as never);
            }}
          />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: spacing.md, marginBottom: spacing.md },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
});
