import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';

import AccentCard from './AccentCard';
import AppText from './AppText';
import DashboardStatRow from './DashboardStatRow';
import SectionHeading from './SectionHeading';
import ToneBadge from './ToneBadge';
import { api } from '../lib/api';
import { sampleFill, TENDENCY_SIGNALS, tendencyBadgeText, tendencyTone } from '../lib/managerTendencies';
import { queryKeys } from '../lib/queryKeys';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors, scrim } from '../theme';
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
  const sample = data?.manager?.sample ?? null;
  const toneColors = { success: colors.success, warning: colors.premium, accent: colors.accent, premium: colors.violet };
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
              <>
                {sample ? (
                  <DashboardStatRow
                    items={[
                      { label: 'Trades', icon: 'swap-horizontal', value: String(sample.trades), valueColor: colors.success },
                      { label: 'Wire moves', icon: 'flash-outline', value: String(sample.wire_moves) },
                      { label: 'Seasons', icon: 'calendar-outline', value: String(sample.seasons) },
                    ]}
                  />
                ) : null}
                <SectionHeading title="Tendencies" />
                {rows.map(([key, title]) => {
                  const signal = signals[key];
                  const tone = toneColors[tendencyTone(signal.label)];
                  const badge = tendencyBadgeText(signal.label);
                  return (
                    <AccentCard key={key} accent={tone} compact style={styles.signal}>
                      <View style={styles.signalHead}>
                        <AppText style={styles.signalTitle}>{title}</AppText>
                        {badge ? <ToneBadge label={badge} color={tone} /> : null}
                      </View>
                      <AppText style={styles.signalSummary}>{signal.summary}</AppText>
                      <View style={styles.meterRow}>
                        <View style={styles.meterTrack}>
                          <View
                            style={[
                              styles.meterFill,
                              { backgroundColor: tone, width: `${Math.round(sampleFill(signal.sample_size, signal.min_sample) * 100)}%` },
                            ]}
                          />
                        </View>
                        <AppText style={styles.muted}>
                          {signal.sample_size} trade{signal.sample_size === 1 ? '' : 's'}
                        </AppText>
                      </View>
                    </AccentCard>
                  );
                })}
              </>
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
      backgroundColor: scrim,
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
    signal: { marginBottom: spacing.sm },
    signalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    meterTrack: { flex: 1, height: 4, borderRadius: radii.pill, backgroundColor: colors.cardBorder, overflow: 'hidden' },
    meterFill: { height: 4, borderRadius: radii.pill },
    signalTitle: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase', color: colors.textSecondary },
    signalSummary: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
    muted: { fontSize: 12, color: colors.textSecondary },
    upsellTitle: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    upsellCta: { fontSize: 13, fontWeight: '700', color: colors.premium, marginTop: spacing.xs },
  });
}
