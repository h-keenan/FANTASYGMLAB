import React, { useEffect, useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import ContentSections, { type ContentSection } from '../components/ContentSections';
import legalContent from '../data/legalContent.json';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, typography, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'LegalPage'>;

interface LegalPage {
  title: string;
  kicker: string;
  note: string;
  sections: ContentSection[];
}

const PAGES = (legalContent as { lastUpdated: string; pages: Record<string, LegalPage> }).pages;
const LAST_UPDATED = (legalContent as { lastUpdated: string }).lastUpdated;

export default function LegalPageScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const page = PAGES[route.params.pageKey];

  useEffect(() => {
    navigation.setOptions({ title: page?.title ?? 'Legal' });
  }, [navigation, page]);

  if (!page) {
    return (
      <View style={styles.root}>
        <GridBackground />
        <View style={[styles.center, { paddingTop: headerHeight }]}>
          <AppText style={styles.error}>This page isn't available.</AppText>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight + spacing.xl }]}>
        <AppText style={styles.kicker}>{page.kicker}</AppText>
        <AppText style={styles.note}>{page.note}</AppText>

        <ContentSections sections={page.sections} />

        <AppText style={styles.lastUpdated}>Last updated {LAST_UPDATED}</AppText>
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.xl,
    },
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
    lastUpdated: {
      ...typography.caption,
      color: colors.textSecondary,
      marginTop: spacing.lg,
      textAlign: 'center',
    },
    error: { color: colors.danger, textAlign: 'center' },
  });
}
