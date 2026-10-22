import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import { api } from '../lib/api';
import { findManagerRow, headlineChips } from '../lib/managerTendencies';
import { queryKeys } from '../lib/queryKeys';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

/**
 * Compact "How this manager trades" chips for a trade partner. Uses the one
 * league-wide summary request (react-query cached, shared by every card);
 * free users get a one-line Premium link, no readable signals renders nothing.
 */
export default function ManagerTendenciesChips({
  leagueId,
  teamName,
  rosterId,
}: {
  leagueId: string;
  teamName: string;
  rosterId?: string | number;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const query = useQuery({
    queryKey: queryKeys.managerTendencies(leagueId),
    queryFn: () => api.getManagerTendencies(leagueId),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const data = query.data;
  if (!data) return null;

  if (!data.is_premium) {
    return (
      <TouchableOpacity onPress={() => navigation.navigate('Paywall')} hitSlop={6}>
        <AppText style={styles.upsell}>How this manager trades · Premium</AppText>
      </TouchableOpacity>
    );
  }
  const chips = headlineChips(findManagerRow(data, teamName, rosterId)?.headline);
  if (chips.length === 0) return null;
  return (
    <View style={styles.row}>
      {chips.map((chip) => (
        <View key={chip} style={styles.chip}>
          <AppText style={styles.chipText} numberOfLines={1}>
            {chip}
          </AppText>
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginTop: spacing.xs },
    chip: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
      borderRadius: radii.sm,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      backgroundColor: colors.backgroundElevated,
    },
    chipText: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
    upsell: { fontSize: 11, fontWeight: '600', color: colors.premium, marginTop: spacing.xs },
  });
}
