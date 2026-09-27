import React, { useCallback, useMemo, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import BrandHeaderBar from '../components/BrandHeaderBar';
import GridBackground from '../components/GridBackground';
import InsightRow from '../components/InsightRow';
import SectionHeading from '../components/SectionHeading';
import { api, type GmPlanFocusArea, type GmPlanResponse } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'GmPlan'>;
type IconName = React.ComponentProps<typeof Ionicons>['name'];

const FOCUS_META: Record<string, { icon: IconName }> = {
  standing: { icon: 'stats-chart-outline' },
  trade_opportunities: { icon: 'swap-horizontal-outline' },
  roster_construction: { icon: 'layers-outline' },
};

/**
 * GM Plan — a season-arc roadmap: where the season currently sits (real
 * week -> phase), the caller's declared Team Situation stance, and what
 * that combination means for how to read the ALREADY-COMPUTED signals
 * below (a real power/draft-capital rank, real trade ideas, real roster
 * construction ranks). A complement to Dashboard's one-off "Next Move"
 * tile, not a replacement — this is the slower, season-level view; Next
 * Move stays the single top tactical action.
 *
 * Deliberately does not read or affect the older "GM Stance" team-strategy
 * system (see /v1/leagues/{id}/gm-stance) — that's a separate, unresolved
 * product question. Every item here traces to a real signal; when a focus
 * area has none, it says so honestly instead of inventing advice (see
 * modules.gm_plan on the backend).
 */
export default function GmPlanScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<GmPlanResponse | null>(null);

  useScreenHeaderTitle(navigation, 'GM Plan', leagueName);

  const load = useCallback(
    async (isRefresh: boolean) => {
      setError(null);
      if (isRefresh) setRefreshing(true);
      try {
        const result = await api.getGmPlan(leagueId, { lens: 'Dynasty' });
        setPlan(result);
      } catch (err) {
        setError(toUserErrorMessage(err, 'Failed to load GM Plan.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [leagueId],
  );

  useFocusEffect(
    useCallback(() => {
      void load(false);
    }, [load]),
  );

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  const quiet = !plan || plan.quiet || plan.focus_areas.length === 0;

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />

      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}
      >
        {error ? <AppText style={styles.error}>{error}</AppText> : null}

        {quiet ? (
          <AnimatedCard style={styles.hero}>
            <AppText style={styles.quietText}>
              {plan?.reason === 'no_sleeper_username_linked'
                ? 'Link your Sleeper account to see a GM Plan for this league.'
                : "We don't have enough to build a GM Plan for this league yet."}
            </AppText>
          </AnimatedCard>
        ) : (
          <>
            <AnimatedCard style={styles.hero} glow>
              <AppText style={styles.phaseLabel}>{(plan!.season_phase_label || '').toUpperCase()}</AppText>
              <AppText style={styles.headline}>{plan!.headline}</AppText>
              {plan!.team_stance_label ? (
                <View style={styles.stancePill}>
                  <Ionicons name="compass-outline" size={12} color={colors.premium} />
                  <AppText style={styles.stancePillText}>{plan!.team_stance_label}</AppText>
                </View>
              ) : null}
            </AnimatedCard>

            {plan!.focus_areas.map((focusArea) => (
              <FocusAreaSection key={focusArea.key} focusArea={focusArea} />
            ))}
          </>
        )}
      </ScrollView>
    </View>
  );
}

function FocusAreaSection({ focusArea }: { focusArea: GmPlanFocusArea }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const icon = FOCUS_META[focusArea.key]?.icon ?? 'ellipse-outline';

  return (
    <View style={styles.section}>
      <SectionHeading title={focusArea.title} icon={icon} />
      {focusArea.framing ? <AppText style={styles.framing}>{focusArea.framing}</AppText> : null}

      {focusArea.status === 'no_signal' ? (
        <AnimatedCard style={styles.card}>
          <InsightRow
            icon="information-circle-outline"
            color={colors.textSecondary}
            headline="Nothing to flag right now"
            detail={focusArea.watch_for}
            last
          />
        </AnimatedCard>
      ) : (
        <AnimatedCard style={styles.card}>
          {focusArea.items.map((item, index) => {
            const last = index === focusArea.items.length - 1;
            if (focusArea.key === 'trade_opportunities' && 'partner_team_name' in item) {
              return (
                <InsightRow
                  key={`${focusArea.key}-${index}`}
                  icon="swap-horizontal-outline"
                  color={colors.premium}
                  headline={`${item.my_player} → ${item.their_player} (${item.partner_team_name})`}
                  detail={item.rationale || item.trade_confidence_label}
                  last={last}
                />
              );
            }
            if ('rank' in item) {
              const tieNote = item.tied ? ' (tied)' : '';
              const weakSpot = 'relative_weak_spot' in item && item.relative_weak_spot;
              return (
                <InsightRow
                  key={`${focusArea.key}-${index}`}
                  icon={weakSpot ? 'alert-circle-outline' : 'checkmark-circle-outline'}
                  color={weakSpot ? colors.danger : colors.accent}
                  headline={`${item.label}: ${item.rank}${item.total_teams ? ` of ${item.total_teams}` : ''}${tieNote}`}
                  detail={weakSpot ? 'Relative weak spot in this league.' : undefined}
                  last={last}
                />
              );
            }
            if ('wins' in item) {
              return (
                <InsightRow
                  key={`${focusArea.key}-${index}`}
                  icon="ribbon-outline"
                  color={colors.accent}
                  headline={`Record: ${item.wins ?? 0}-${item.losses ?? 0}${item.ties ? `-${item.ties}` : ''}`}
                  last={last}
                />
              );
            }
            return null;
          })}
        </AnimatedCard>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
    scrollContent: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.xl },
    error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
    hero: { marginBottom: spacing.lg, gap: spacing.xs },
    quietText: { fontSize: 14, color: colors.textSecondary, lineHeight: 20 },
    phaseLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 0.6, color: colors.premium },
    headline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, lineHeight: 22 },
    stancePill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      alignSelf: 'flex-start',
      marginTop: spacing.xs,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      borderRadius: radii.pill,
      backgroundColor: colors.premiumMuted,
    },
    stancePillText: { fontSize: 11, fontWeight: '700', color: colors.premium },
    section: { marginBottom: spacing.lg },
    framing: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.sm },
    card: { paddingVertical: spacing.xs },
  });
}
