import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';
import { useHeaderHeight } from '@react-navigation/elements';

import ContentSections, { type ContentSection } from '../components/ContentSections';
import methodologyContent from '../data/methodologyContent.json';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, typography, type ThemeColors } from '../theme';

interface MethodologyContent {
  title: string;
  kicker: string;
  note: string;
  sections: ContentSection[];
}

const CONTENT = methodologyContent as MethodologyContent;

export default function HowWeEvaluateScreen() {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight + spacing.xl }]}>
        <AppText style={styles.kicker}>{CONTENT.kicker}</AppText>
        <AppText style={styles.note}>{CONTENT.note}</AppText>
        <ContentSections sections={CONTENT.sections} />
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    // Was solid `colors.background` here, which fully covered GridBackground
    // and left the screen with no visible wash — matches the transparent
    // pattern Dashboard/MyTeam/TradeHub/Teams already use so the shared
    // backdrop actually renders instead of being painted over.
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
    kicker: {
      ...typography.kicker,
      color: colors.accent,
      textTransform: 'uppercase',
      marginBottom: spacing.xs,
    },
    note: {
      ...typography.body,
      color: colors.textSecondary,
      marginBottom: spacing.xl,
      lineHeight: 22,
    },
  });
}
