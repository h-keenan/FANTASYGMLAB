import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { useHeaderHeight } from '@react-navigation/elements';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AccentCard from '../components/AccentCard';
import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import BrandHeaderBar from '../components/BrandHeaderBar';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import PremiumLock from '../components/PremiumLock';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import ToneBadge from '../components/ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  BAND_LABEL,
  bandTone,
  CONFIDENCE_LABEL,
  DRAFT_ORDER_OPTIONS,
  INTERPRETATION_LABEL,
  integrityReasonMessage,
  integritySummaryLine,
  splitTeams,
  type CommissionerIntegrityResponse,
  type DraftOrderRule,
  type IntegrityBand,
  type IntegrityCollusionPair,
  type IntegrityInactiveManager,
  type IntegrityTeam,
} from '../lib/commissionerIntegrity';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Commissioner'>;

/**
 * Commissioner: league integrity (lineups, tanking signals, lopsided repeat
 * trades, inactive managers) for the league's commissioner. Every number is
 * read from the server (modules/league_integrity.py); signals are prompts to
 * look, so each card lists the innocent explanations beside the evidence.
 * Mirrors web-next's CommissionerContent and shares lib/commissionerIntegrity.
 */
export default function CommissionerScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [draftOrder, setDraftOrder] = useState<DraftOrderRule>('unknown');
  useScreenHeaderTitle(navigation, 'Commissioner', leagueName);

  const query = useQuery({
    queryKey: queryKeys.commissionerIntegrity(leagueId, draftOrder),
    queryFn: () => api.getCommissionerIntegrity(leagueId, draftOrder),
    staleTime: 5 * 60 * 1000,
  });
  const data = query.data;

  const toneColor = (band: IntegrityBand): string => {
    const tone = bandTone(band);
    return tone === 'success' ? colors.success : tone === 'warning' ? colors.warning : tone === 'danger' ? colors.danger : colors.textTertiary;
  };

  let body: React.ReactNode;
  if (query.isLoading) {
    body = <BrandedSpinner style={styles.center} />;
  } else if (query.error || !data) {
    body = <ErrorState title="Couldn't load League integrity" message={toUserErrorMessage(query.error, 'Failed to load League integrity.')} />;
  } else if (data.is_premium === false) {
    body = (
      <PremiumLock
        feature="commissioner"
        title={data.upsell?.title || 'Spot tanking and lineup problems early'}
        description={data.upsell?.body || 'League integrity is a Pro feature for commissioners.'}
      />
    );
  } else if (data.reason) {
    body = <EmptyState icon="shield-checkmark-outline" title="Nothing to show yet" subtitle={integrityReasonMessage(data.reason)} />;
  } else {
    body = <IntegrityBody data={data} draftOrder={draftOrder} onDraftOrder={setDraftOrder} toneColor={toneColor} styles={styles} />;
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>{body}</ScrollView>
    </View>
  );
}

function Bullets({ title, items, styles }: { title: string; items: string[]; styles: ReturnType<typeof createStyles> }) {
  if (!items.length) return null;
  return (
    <View style={styles.bullets}>
      <AppText style={styles.bulletsTitle}>{title}</AppText>
      {items.map((text) => (
        <AppText key={text} style={styles.bullet}>
          {'•'} {text}
        </AppText>
      ))}
    </View>
  );
}

function EfficiencyBars({ team, colors, styles }: { team: IntegrityTeam; colors: ThemeColors; styles: ReturnType<typeof createStyles> }) {
  if (!team.series.length) return null;
  return (
    <View style={styles.bars} accessibilityLabel="Lineup efficiency by week">
      {team.series.map((point) => {
        const pct = Math.max(0.05, Math.min(1, point.efficiency ?? 0));
        return (
          <View key={point.week} style={styles.barCol}>
            <View
              style={{
                width: '100%',
                height: Math.round(pct * 28),
                borderRadius: 2,
                backgroundColor: point.flagged ? colors.warning : colors.textTertiary,
                opacity: point.flagged ? 1 : 0.45,
              }}
            />
            <AppText style={styles.barLabel}>{point.week}</AppText>
          </View>
        );
      })}
    </View>
  );
}

function TeamCard({
  team,
  toneColor,
  colors,
  styles,
}: {
  team: IntegrityTeam;
  toneColor: (band: IntegrityBand) => string;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
}) {
  const [open, setOpen] = useState(team.band === 'strong');
  const expandable = team.band === 'strong' || team.band === 'worth_a_look';
  return (
    <AccentCard accent={toneColor(team.band)}>
      <View style={styles.cardHead}>
        <View style={styles.flex}>
          <AppText style={styles.teamName}>{team.team_name}</AppText>
          <AppText style={styles.muted}>
            {team.owner_name}
            {team.weeks.evaluated ? ` · ${team.weeks.flagged} of ${team.weeks.evaluated} weeks flagged` : ''}
          </AppText>
        </View>
        <ToneBadge label={BAND_LABEL[team.band]} color={toneColor(team.band)} />
      </View>
      {expandable ? (
        <>
          {INTERPRETATION_LABEL[team.interpretation] ? (
            <AppText style={styles.body}>
              {INTERPRETATION_LABEL[team.interpretation]} · {CONFIDENCE_LABEL[team.confidence]}
            </AppText>
          ) : null}
          <TouchableOpacity onPress={() => setOpen((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: open }}>
            <AppText style={styles.link}>{open ? 'Hide the evidence' : 'Show the evidence'}</AppText>
          </TouchableOpacity>
          {open ? (
            <>
              <Bullets title="Evidence" items={team.evidence.map((e) => e.text)} styles={styles} />
              <EfficiencyBars team={team} colors={colors} styles={styles} />
              <Bullets title="Could be innocent" items={team.innocent_explanations} styles={styles} />
            </>
          ) : null}
        </>
      ) : null}
    </AccentCard>
  );
}

function IntegrityBody({
  data,
  draftOrder,
  onDraftOrder,
  toneColor,
  styles,
}: {
  data: CommissionerIntegrityResponse;
  draftOrder: DraftOrderRule;
  onDraftOrder: (value: DraftOrderRule) => void;
  toneColor: (band: IntegrityBand) => string;
  styles: ReturnType<typeof createStyles>;
}) {
  const { colors } = useThemeMode();
  const { flagged, rest } = splitTeams(data.teams);
  const [showRest, setShowRest] = useState(false);
  return (
    <View style={styles.stack}>
      <AppText style={styles.body}>{integritySummaryLine(data)}</AppText>
      <View style={styles.bullets}>
        <AppText style={styles.bulletsTitle}>How is your draft order set?</AppText>
        <SegmentedTabBar
          options={DRAFT_ORDER_OPTIONS.map((o) => ({ key: o.value, label: o.label }))}
          active={draftOrder}
          onChange={onDraftOrder}
        />
        <AppText style={styles.muted}>
          Sleeper does not publish this, so it changes how a flagged team is described, not the lineup math.
        </AppText>
      </View>

      {flagged.length ? (
        <View style={styles.stack}>
          <SectionHeading title="Worth a look" />
          {flagged.map((team) => (
            <TeamCard key={team.roster_id} team={team} toneColor={toneColor} colors={colors} styles={styles} />
          ))}
        </View>
      ) : null}

      {data.collusion.length ? (
        <View style={styles.stack}>
          <SectionHeading
            title="Repeated lopsided trades"
            caption="Same two managers, repeated one-sided trades. Picks are not valued, so trades with picks are never flagged."
          />
          {data.collusion.map((pair) => (
            <CollusionCard key={pair.roster_ids.join('-')} pair={pair} toneColor={toneColor} styles={styles} />
          ))}
        </View>
      ) : null}

      {data.inactive.length ? (
        <View style={styles.stack}>
          <SectionHeading title="Possibly inactive" />
          {data.inactive.map((m) => (
            <InactiveCard key={m.roster_id} manager={m} accent={colors.warning} styles={styles} />
          ))}
        </View>
      ) : null}

      {rest.length ? (
        <View style={styles.stack}>
          <SectionHeading title="Everyone else" />
          <TouchableOpacity onPress={() => setShowRest((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: showRest }}>
            <AppText style={styles.link}>{showRest ? 'Hide teams' : `Show ${rest.length} team${rest.length === 1 ? '' : 's'}`}</AppText>
          </TouchableOpacity>
          {showRest
            ? rest.map((team) => <TeamCard key={team.roster_id} team={team} toneColor={toneColor} colors={colors} styles={styles} />)
            : null}
        </View>
      ) : null}

      {data.limits?.length ? <Bullets title="What this can and can't tell you" items={data.limits} styles={styles} /> : null}
    </View>
  );
}

function CollusionCard({
  pair,
  toneColor,
  styles,
}: {
  pair: IntegrityCollusionPair;
  toneColor: (band: IntegrityBand) => string;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <AccentCard accent={toneColor(pair.band)}>
      <View style={styles.cardHead}>
        <AppText style={[styles.teamName, styles.flex]}>
          {pair.giver_name} and {pair.beneficiary_name}
        </AppText>
        <ToneBadge label={BAND_LABEL[pair.band]} color={toneColor(pair.band)} />
      </View>
      <AppText style={styles.body}>
        {pair.trades_between} trades between them; {pair.lopsided_same_direction} lopsided in {pair.beneficiary_name}&rsquo;s favor ·{' '}
        {CONFIDENCE_LABEL[pair.confidence]}
      </AppText>
      <Bullets title="Evidence" items={pair.evidence} styles={styles} />
      <Bullets title="Could be innocent" items={pair.innocent_explanations} styles={styles} />
    </AccentCard>
  );
}

function InactiveCard({
  manager,
  accent,
  styles,
}: {
  manager: IntegrityInactiveManager;
  accent: string;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <AccentCard accent={accent}>
      <AppText style={styles.teamName}>{manager.team_name}</AppText>
      <Bullets title="Evidence" items={manager.evidence} styles={styles} />
      <Bullets title="Could be innocent" items={manager.innocent_explanations} styles={styles} />
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.lg },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
    stack: { gap: spacing.md },
    flex: { flex: 1 },
    cardHead: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.sm },
    teamName: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    body: { fontSize: 14, color: colors.textSecondary },
    muted: { fontSize: 12, color: colors.textTertiary },
    link: { fontSize: 12, fontWeight: '700', color: colors.accent },
    bullets: { gap: spacing.xs },
    bulletsTitle: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8, color: colors.textTertiary },
    bullet: { fontSize: 13, color: colors.textSecondary },
    bars: { flexDirection: 'row', alignItems: 'flex-end', gap: 4, height: 44 },
    barCol: { flex: 1, alignItems: 'center', gap: 2 },
    barLabel: { fontSize: 10, color: colors.textTertiary },
  });
}
