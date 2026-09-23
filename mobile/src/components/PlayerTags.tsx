import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

export interface PlayerTagSpec {
  key: string;
  label: string;
  color: string;
  /** 'solid' = filled pill with contrast text (tier); 'outline' = tinted
   * text on a translucent outline (prime window / opportunity). Matches the
   * concept sheet's own visual hierarchy: the tier chip reads as the
   * strongest classification, the other two as secondary context. */
  variant: 'solid' | 'outline';
  contrastText?: string;
}

/**
 * The player's classification row — tier ("GENERATIONAL"), prime-window
 * ("In Prime · 20-25"), and opportunity ("Elite Opportunity") pills, wrapped
 * into one row. Every value is computed by the caller from real
 * QuickViewStats/tier data — this component only renders whatever tags it's
 * given, dynamically, for whichever player is on screen.
 */
export default function PlayerTags({ tags, align = 'flex-start' }: { tags: PlayerTagSpec[]; align?: 'flex-start' | 'center' }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (tags.length === 0) return null;
  return (
    <View style={[styles.row, { justifyContent: align === 'center' ? 'center' : 'flex-start' }]}>
      {tags.map((tag) =>
        tag.variant === 'solid' ? (
          <View key={tag.key} style={[styles.solidPill, { backgroundColor: tag.color }]}>
            <AppText style={[styles.solidText, { color: tag.contrastText ?? '#0D1117' }]}>{tag.label}</AppText>
          </View>
        ) : (
          <View key={tag.key} style={[styles.outlinePill, { borderColor: tag.color }]}>
            <AppText style={[styles.outlineText, { color: tag.color }]}>{tag.label}</AppText>
          </View>
        ),
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.xs },
    solidPill: { paddingHorizontal: spacing.sm, paddingVertical: 3, borderRadius: radii.pill },
    solidText: { fontSize: 11, fontWeight: '800', letterSpacing: 0.3 },
    outlinePill: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radii.pill,
      borderWidth: 1,
    },
    outlineText: { fontSize: 11, fontWeight: '700' },
  });
}
