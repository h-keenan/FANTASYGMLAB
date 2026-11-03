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
 * (Alerts, Matchup). Mirrors web-next's components/NextSteps.tsx: keep the
 * step list and copy identical.
 */
export type NextStepKey = 'matchup' | 'waivers' | 'trade-hub' | 'my-team';

export const NEXT_STEPS: Record<NextStepKey, { label: string; route: 'Matchup' | 'Waivers' | 'Trades' | 'MyTeam' }> = {
  matchup: { label: 'Check your lineup', route: 'Matchup' },
  waivers: { label: 'Find a waiver add', route: 'Waivers' },
  'trade-hub': { label: 'See trade ideas', route: 'Trades' },
  'my-team': { label: 'Review your roster', route: 'MyTeam' },
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
            onPress={() => navigation.navigate(NEXT_STEPS[step].route, { leagueId, leagueName })}
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
