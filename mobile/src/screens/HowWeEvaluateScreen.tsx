import React from 'react';
import { ScrollView, StyleSheet, Text } from 'react-native';

import ContentSections, { type ContentSection } from '../components/ContentSections';
import methodologyContent from '../data/methodologyContent.json';
import { useOrbClearance } from '../lib/orbLayout';
import { colors, spacing } from '../theme';

interface MethodologyContent {
  title: string;
  kicker: string;
  note: string;
  sections: ContentSection[];
}

const CONTENT = methodologyContent as MethodologyContent;

export default function HowWeEvaluateScreen() {
  const orbClearance = useOrbClearance();

  return (
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <Text style={styles.kicker}>{CONTENT.kicker}</Text>
      <Text style={styles.note}>{CONTENT.note}</Text>
      <ContentSections sections={CONTENT.sections} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  kicker: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.accent,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: spacing.xs,
  },
  note: {
    fontSize: 15,
    color: colors.textSecondary,
    marginBottom: spacing.xl,
    lineHeight: 21,
  },
});
