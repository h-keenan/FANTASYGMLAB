import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { colors, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'More'>;

const LEGAL_ITEMS: Array<{ pageKey: string; label: string; icon: React.ComponentProps<typeof Ionicons>['name'] }> = [
  { pageKey: 'about_disclaimer', label: 'About / Disclaimer', icon: 'information-circle-outline' },
  { pageKey: 'terms', label: 'Terms of Use', icon: 'document-text-outline' },
  { pageKey: 'privacy', label: 'Privacy Policy', icon: 'shield-checkmark-outline' },
  { pageKey: 'no_affiliation', label: 'No-Affiliation Disclaimer', icon: 'alert-circle-outline' },
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
          <View style={styles.labelGroup}>
            <Ionicons name={item.icon} size={18} color={colors.accent} style={styles.icon} />
            <Text style={styles.label}>{item.label}</Text>
          </View>
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
  labelGroup: { flexDirection: 'row', alignItems: 'center', flexShrink: 1 },
  icon: { marginRight: spacing.sm },
  label: { fontSize: 16, color: colors.textPrimary, flexShrink: 1 },
  chevron: { fontSize: 20, color: colors.textSecondary },
});
