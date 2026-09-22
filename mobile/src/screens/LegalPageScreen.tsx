import React, { useEffect, useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import ContentSections, { type ContentSection } from '../components/ContentSections';
import legalContent from '../data/legalContent.json';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const page = PAGES[route.params.pageKey];

  useEffect(() => {
    navigation.setOptions({ title: page?.title ?? 'Legal' });
  }, [navigation, page]);

  if (!page) {
    return (
      <View style={styles.center}>
        <AppText style={styles.error}>This page isn't available.</AppText>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <AppText style={styles.kicker}>{page.kicker}</AppText>
      <AppText style={styles.note}>{page.note}</AppText>

      <ContentSections sections={page.sections} />

      <AppText style={styles.lastUpdated}>Last updated {LAST_UPDATED}</AppText>
    </ScrollView>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.background,
      padding: spacing.xl,
    },
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
    lastUpdated: {
      fontSize: 12,
      color: colors.textSecondary,
      marginTop: spacing.lg,
      textAlign: 'center',
    },
    error: { color: colors.danger, textAlign: 'center' },
  });
}
