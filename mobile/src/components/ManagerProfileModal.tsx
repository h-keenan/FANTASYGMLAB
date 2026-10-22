import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';

import AppText from './AppText';
import { api } from '../lib/api';
import { TENDENCY_SIGNALS } from '../lib/managerTendencies';
import { queryKeys } from '../lib/queryKeys';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

interface Props {
  visible: boolean;
  onClose: () => void;
  leagueId: string;
  rosterId: string | number;
  teamName: string;
}

/** Manager profile (League Rankings): every readable signal with its
 * evidence line. Fetches only while open. */
export default function ManagerProfileModal({ visible, onClose, leagueId, rosterId, teamName }: Props) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const query = useQuery({
    queryKey: queryKeys.managerTendencyDetail(leagueId, rosterId),
    queryFn: () => api.getManagerTendencyDetail(leagueId, rosterId),
    enabled: visible,
    staleTime: 5 * 60 * 1000,
  });
  const data = query.data;
  const signals = data?.manager?.signals ?? {};
  const rows = TENDENCY_SIGNALS.filter(([key]) => signals[key]?.status === 'ok');

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.headerRow}>
            <View style={styles.titleGroup}>
              <AppText style={styles.kicker}>How this manager trades</AppText>
              <AppText style={styles.title} numberOfLines={1}>
                {teamName}
              </AppText>
            </View>
            <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close">
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </Pressable>
          </View>
          <ScrollView style={styles.body}>
            {query.isError ? (
              <AppText style={styles.muted}>Couldn&apos;t load this profile.</AppText>
            ) : !data ? (
              <AppText style={styles.muted}>Loading…</AppText>
            ) : !data.is_premium ? (
              <TouchableOpacity
                onPress={() => {
                  onClose();
                  navigation.navigate('Paywall');
                }}
              >
                <AppText style={styles.upsellTitle}>{data.upsell?.title ?? 'Manager Tendencies'}</AppText>
                <AppText style={styles.upsellCta}>Upgrade</AppText>
              </TouchableOpacity>
            ) : rows.length === 0 ? (
              <AppText style={styles.muted}>Not enough trade history yet.</AppText>
            ) : (
              rows.map(([key, title]) => (
                <View key={key} style={styles.signal}>
                  <AppText style={styles.signalTitle}>{title}</AppText>
                  <AppText style={styles.signalSummary}>{signals[key].summary}</AppText>
                  <AppText style={styles.muted}>
                    {signals[key].sample_size} trade{signals[key].sample_size === 1 ? '' : 's'} analyzed
                  </AppText>
                </View>
              ))
            )}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: 'rgba(0,0,0,0.6)',
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.lg,
    },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
      width: '100%',
      maxWidth: 420,
      maxHeight: '80%',
    },
    headerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.md },
    titleGroup: { flex: 1, marginRight: spacing.sm },
    kicker: { fontSize: 11, color: colors.textSecondary },
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
    body: { flexGrow: 0 },
    signal: { marginBottom: spacing.md },
    signalTitle: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', color: colors.textSecondary },
    signalSummary: { fontSize: 14, color: colors.textPrimary },
    muted: { fontSize: 12, color: colors.textSecondary },
    upsellTitle: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    upsellCta: { fontSize: 13, fontWeight: '700', color: colors.premium, marginTop: spacing.xs },
  });
}
