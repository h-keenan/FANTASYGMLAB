import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';

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
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <AppText style={styles.kicker}>{CONTENT.kicker}</AppText>
        <AppText style={styles.note}>{CONTENT.note}</AppText>
        <ContentSections sections={CONTENT.sections} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
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
