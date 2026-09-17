import React, { useEffect } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import ContentSections, { type ContentSection } from '../components/ContentSections';
import legalContent from '../data/legalContent.json';
import { useOrbClearance } from '../lib/orbLayout';
import { colors, spacing } from '../theme';
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
  const page = PAGES[route.params.pageKey];

  useEffect(() => {
    navigation.setOptions({ title: page?.title ?? 'Legal' });
  }, [navigation, page]);

  if (!page) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>This page isn't available.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <Text style={styles.kicker}>{page.kicker}</Text>
      <Text style={styles.note}>{page.note}</Text>

      <ContentSections sections={page.sections} />

      <Text style={styles.lastUpdated}>Last updated {LAST_UPDATED}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
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
