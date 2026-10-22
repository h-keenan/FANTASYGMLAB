import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { type ThemeColors } from '../theme';

/**
 * The square draft-pick plate ("R1" over "#3"), shared by every pick row
 * (owner decision 4). Mirrors web-next's PickPlate.
 */
export default function PickPlate({ round, pickNo }: { round?: number | null; pickNo?: number | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const top = round ? `R${round}` : pickNo ? `#${pickNo}` : 'PICK';
  const bottom = round && pickNo ? `#${pickNo}` : null;
  return (
    <View style={styles.plate}>
      <AppText style={styles.text}>{top}</AppText>
      {bottom ? <AppText style={styles.text}>{bottom}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    plate: {
      width: 38,
      height: 38,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.backgroundElevated,
      borderWidth: 1,
      borderColor: colors.border,
      marginRight: 8,
    },
    text: { fontSize: 11, fontWeight: '800', color: colors.accent, lineHeight: 13 },
  });
}
