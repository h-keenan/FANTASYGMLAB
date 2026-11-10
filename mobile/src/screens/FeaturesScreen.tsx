import React, { useEffect, useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { useHeaderHeight } from '@react-navigation/elements';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useIsRestoring, useQuery } from '@tanstack/react-query';

import AnimatedCard from '../components/AnimatedCard';
import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import SectionHeading from '../components/SectionHeading';
import ToneBadge from '../components/ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { FEATURE_GROUPS, FEATURE_ITEMS, featureTarget, type FeatureLeague } from '../lib/featureCatalog';
import { useLastLeague } from '../lib/useLastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { getEntitlementTier, isAtLeast, PRO } from '../lib/revenuecat';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Features'>;
type IconName = React.ComponentProps<typeof IconCircle>['name'];

/**
 * "What FantasyDesk can do": every feature grouped by what the user wants to
 * do, one line each, opening for their current league. Web twin:
 * web-next/src/components/FeaturesContent.tsx. The list is
 * lib/featureCatalog.ts. League = the one passed in (Dashboard's Start here
 * card), otherwise the last league opened. Pro tags follow the GM orb: shown
 * only for a confirmed Free plan.
 */
export default function FeaturesScreen({ navigation, route }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const lastLeague = useLastLeague();
  const passed = route.params?.leagueId && route.params?.leagueName ? { leagueId: route.params.leagueId, leagueName: route.params.leagueName } : null;
  const league: FeatureLeague | null = passed ?? lastLeague;

  const isRestoring = useIsRestoring();
  const planQuery = useQuery({ queryKey: queryKeys.mePlan(), queryFn: () => api.getMe(), enabled: !isRestoring, staleTime: 5 * 60 * 1000 });
  const [storeSubscriber, setStoreSubscriber] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getEntitlementTier()
      .then((tier) => {
        if (!cancelled) setStoreSubscriber(isAtLeast(tier, PRO));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  const showPro = planQuery.data?.user.profile_status === 'ok' && planQuery.data.user.entitlement !== 'premium' && !storeSubscriber;

  const colorFor: Record<string, string> = {
    accent: colors.accent,
    danger: colors.danger,
    success: colors.success,
    violet: colors.violet,
    premium: colors.premium,
  };

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingTop: headerHeight + spacing.md, paddingBottom: orbClearance }]}>
        <AppText style={styles.subtitle}>
          {league ? `Tap anything to open it for ${league.leagueName}.` : 'Open a league from Home first. League tools open for the league you choose.'}
        </AppText>
        {FEATURE_GROUPS.map((group, groupIndex) => (
          <View key={group.id}>
            <SectionHeading title={group.title} topGap={groupIndex === 0 ? 0 : spacing.md} />
            <AnimatedCard style={styles.groupCard}>
              {FEATURE_ITEMS.filter((item) => item.group === group.id).map((item, index) => (
                <TouchableOpacity
                  key={item.id}
                  accessibilityRole="button"
                  accessibilityLabel={item.name}
                  accessibilityHint={item.line}
                  activeOpacity={0.7}
                  onPress={() => {
                    const target = featureTarget(item, league);
                    if (!target) {
                      Alert.alert('Select a league first', 'Open a league from Home, then come back to open this.');
                      return;
                    }
                    (navigation.navigate as (name: string, params?: object) => void)(target.name, target.params);
                  }}
                  style={[styles.row, index > 0 && styles.rowDivider]}
                >
                  <IconCircle name={item.icon as IconName} color={colorFor[item.color]} style={styles.icon} />
                  <View style={styles.rowText}>
                    <View style={styles.titleRow}>
                      <AppText style={styles.name}>{item.name}</AppText>
                      {item.pro && showPro ? <ToneBadge label="Pro" color={colors.premium} size="xs" /> : null}
                    </View>
                    <AppText style={styles.line}>{item.line}</AppText>
                    {item.extra && showPro ? <AppText style={styles.extra}>{item.extra}</AppText> : null}
                  </View>
                  <AppText style={styles.chevron}>{'›'}</AppText>
                </TouchableOpacity>
              ))}
            </AnimatedCard>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { paddingHorizontal: spacing.lg },
    subtitle: { fontSize: 15.5, color: colors.textSecondary, marginBottom: spacing.md },
    groupCard: { padding: spacing.md, paddingVertical: 0 },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: spacing.sm },
    rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    icon: {},
    rowText: { flex: 1, minWidth: 0 },
    titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    name: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    line: { fontSize: 14.5, color: colors.textSecondary },
    extra: { fontSize: 13.5, color: colors.textTertiary },
    chevron: { fontSize: 19.5, color: colors.accent },
  });
}
