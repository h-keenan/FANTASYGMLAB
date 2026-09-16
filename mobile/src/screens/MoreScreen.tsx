import React, { useState } from 'react';
import { ActivityIndicator, Alert, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import { api } from '../lib/api';
import { syncPushToken } from '../lib/pushNotifications';
import { colors, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'More'>;

const LEGAL_ITEMS: Array<{ pageKey: string; label: string; icon: React.ComponentProps<typeof Ionicons>['name'] }> = [
  { pageKey: 'about_disclaimer', label: 'About / Disclaimer', icon: 'information-circle-outline' },
  { pageKey: 'terms', label: 'Terms of Use', icon: 'document-text-outline' },
  { pageKey: 'privacy', label: 'Privacy Policy', icon: 'shield-checkmark-outline' },
  { pageKey: 'subscription_terms', label: 'Subscription Terms', icon: 'card-outline' },
  { pageKey: 'no_affiliation', label: 'No-Affiliation Disclaimer', icon: 'alert-circle-outline' },
];

export default function MoreScreen({ navigation }: Props) {
  const [sendingTestPush, setSendingTestPush] = useState(false);

  const onSendTestPush = async () => {
    setSendingTestPush(true);
    try {
      await syncPushToken();
      const result = await api.sendTestPush();
      if (result.ok) {
        Alert.alert('Test notification sent', 'It should arrive shortly.');
      } else if (result.reason === 'no_registered_tokens') {
        Alert.alert(
          'No device registered yet',
          "We couldn't find a push token for this device. Make sure notifications are allowed for this app in Settings, then try again.",
        );
      } else {
        Alert.alert('Could not send test notification', 'Please try again in a moment.');
      }
    } catch {
      Alert.alert('Could not send test notification', 'Please try again in a moment.');
    } finally {
      setSendingTestPush(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.sectionLabel}>Notifications</Text>
      <TouchableOpacity style={styles.row} onPress={onSendTestPush} disabled={sendingTestPush}>
        <View style={styles.labelGroup}>
          <Ionicons name="notifications-outline" size={18} color={colors.accent} style={styles.icon} />
          <Text style={styles.label}>Send test notification</Text>
        </View>
        {sendingTestPush ? <ActivityIndicator size="small" color={colors.accent} /> : <Text style={styles.chevron}>{'›'}</Text>}
      </TouchableOpacity>

      <Text style={styles.sectionLabel}>Legal</Text>
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
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xs,
  },
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
