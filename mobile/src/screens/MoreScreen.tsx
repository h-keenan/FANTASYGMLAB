import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { colors, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'More'>;

const LEGAL_ITEMS: Array<{ pageKey: string; label: string }> = [
  { pageKey: 'about_disclaimer', label: 'About / Disclaimer' },
  { pageKey: 'terms', label: 'Terms of Use' },
  { pageKey: 'privacy', label: 'Privacy Policy' },
  { pageKey: 'no_affiliation', label: 'No-Affiliation Disclaimer' },
];

export default function MoreScreen({ navigation }: Props) {
  return (
    <View style={styles.container}>
      {LEGAL_ITEMS.map((item) => (
        <TouchableOpacity
          key={item.pageKey}
          style={styles.row}
          onPress={() => navigation.navigate('LegalPage', { pageKey: item.pageKey })}
        >
          <Text style={styles.label}>{item.label}</Text>
          <Text style={styles.chevron}>{'›'}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  label: { fontSize: 16, color: colors.textPrimary },
  chevron: { fontSize: 20, color: colors.textSecondary },
});
