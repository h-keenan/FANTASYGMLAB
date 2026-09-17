import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '../theme';

export interface ContentSection {
  title: string;
  paragraphs: string[];
  bullets: string[];
}

/** Shared renderer for static prose pages (Legal, How We Evaluate) that
 * ship as generator-backed JSON — see scripts/export_legal_content.py and
 * scripts/export_methodology_content.py. */
export default function ContentSections({ sections }: { sections: ContentSection[] }) {
  return (
    <>
      {sections.map((section) => (
        <View key={section.title} style={styles.section}>
          <Text style={styles.sectionTitle}>{section.title}</Text>
          {section.paragraphs.map((paragraph) => (
            <Text key={paragraph} style={styles.paragraph}>
              {paragraph}
            </Text>
          ))}
          {section.bullets.map((bullet) => (
            <View key={bullet} style={styles.bulletRow}>
              <Text style={styles.bulletMark}>{'•'}</Text>
              <Text style={styles.bulletText}>{bullet}</Text>
            </View>
          ))}
        </View>
      ))}
    </>
  );
}

const styles = StyleSheet.create({
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
