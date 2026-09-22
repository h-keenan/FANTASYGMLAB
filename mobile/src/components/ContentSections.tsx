import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

export interface ContentSection {
  title: string;
  paragraphs: string[];
  bullets: string[];
}

/** Shared renderer for static prose pages (Legal, How We Evaluate) that
 * ship as generator-backed JSON — see scripts/export_legal_content.py and
 * scripts/export_methodology_content.py. */
export default function ContentSections({ sections }: { sections: ContentSection[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <>
      {sections.map((section) => (
        <View key={section.title} style={styles.section}>
          <AppText style={styles.sectionTitle}>{section.title}</AppText>
          {section.paragraphs.map((paragraph) => (
            <AppText key={paragraph} style={styles.paragraph}>
              {paragraph}
            </AppText>
          ))}
          {section.bullets.map((bullet) => (
            <View key={bullet} style={styles.bulletRow}>
              <AppText style={styles.bulletMark}>{'•'}</AppText>
              <AppText style={styles.bulletText}>{bullet}</AppText>
            </View>
          ))}
        </View>
      ))}
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    section: { marginBottom: spacing.lg },
    sectionTitle: {
      fontSize: 16,
      fontWeight: '700',
      color: colors.textPrimary,
      marginBottom: spacing.sm,
    },
    paragraph: {
      fontSize: 14,
      color: colors.textPrimary,
      lineHeight: 21,
      marginBottom: spacing.sm,
    },
    bulletRow: { flexDirection: 'row', marginBottom: spacing.xs, paddingLeft: spacing.xs },
    bulletMark: { color: colors.textSecondary, marginRight: spacing.sm },
    bulletText: { flex: 1, fontSize: 14, color: colors.textPrimary, lineHeight: 20 },
  });
}
