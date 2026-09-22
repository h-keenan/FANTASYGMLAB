import React, { useEffect, useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import CircularProgressRing from '../components/CircularProgressRing';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import GridBackground from '../components/GridBackground';
import IconCircle from '../components/IconCircle';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'PickDetail'>;

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

/** Same three round-slot buckets modules/trade_ideas.py projects over, in
 * board order (a pick that lands early in the round is the valuable one). */
function buckets(colors: ThemeColors) {
  return [
    { key: 'early', label: 'Early', color: colors.success },
    { key: 'mid', label: 'Mid', color: colors.accent },
    { key: 'late', label: 'Late', color: colors.textSecondary },
  ] as const;
}

/** Confidence here is the probability mass sitting on the single most likely
 * slot bucket — the model's own `projection_confidence`, not a rescaling of
 * it. The thresholds only pick a color/word for it. */
function confidenceIdentity(confidence: number, colors: ThemeColors): { color: string; word: string } {
  if (confidence >= 0.6) return { color: colors.success, word: 'High' };
  if (confidence >= 0.45) return { color: colors.accent, word: 'Moderate' };
  return { color: colors.premium, word: 'Low' };
}

function num(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/** "×1.04" / "×0.77" — multipliers read far faster as a signed deviation from
 * neutral than as a bare decimal, and the tint says at a glance whether this
 * driver is adding or removing value. */
function MultiplierRow({
  label,
  multiplier,
  note,
}: {
  label: string;
  multiplier: number | null;
  note: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const delta = multiplier === null ? 0 : multiplier - 1;
  const neutral = Math.abs(delta) < 0.005;
  const color = neutral || multiplier === null
    ? colors.textSecondary
    : delta > 0
      ? colors.success
      : colors.danger;
  return (
    <View style={styles.driverRow}>
      <View style={styles.driverText}>
        <AppText style={styles.driverLabel}>{label}</AppText>
        <AppText style={styles.driverNote}>{note}</AppText>
      </View>
      <View style={styles.driverValueBlock}>
        <AppText style={[styles.driverValue, { color }]}>
          {multiplier === null ? '—' : `×${multiplier.toFixed(2)}`}
        </AppText>
        {multiplier !== null && !neutral ? (
          <AppText style={[styles.driverDelta, { color }]}>
            {delta > 0 ? '+' : ''}
            {Math.round(delta * 100)}%
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

function BucketBar({ label, percent, color }: { label: string; percent: number; color: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.bucketRow}>
      <AppText style={styles.bucketLabel}>{label}</AppText>
      <View style={styles.bucketTrack}>
        <View style={[styles.bucketFill, { width: `${Math.max(2, percent)}%`, backgroundColor: color }]} />
      </View>
      <AppText style={styles.bucketPercent}>{Math.round(percent)}%</AppText>
    </View>
  );
}

function SectionHeading({ title, icon }: { title: string; icon: IoniconName }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.sectionHeadingRow}>
      <Ionicons name={icon} size={15} color={colors.accent} style={styles.sectionHeadingIcon} />
      <AppText style={styles.sectionTitle}>{title}</AppText>
    </View>
  );
}

function StatCell({ label, value }: { label: string; value: string | number | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const display = value === null || value === undefined || value === '' ? '—' : value;
  return (
    <View style={styles.statCell}>
      <AppText style={styles.statCellLabel} numberOfLines={1}>
        {label}
      </AppText>
      <AppText style={styles.statCellValue} numberOfLines={1}>
        {display}
      </AppText>
    </View>
  );
}

function StatGrid({ items }: { items: Array<{ label: string; value: string | number | null }> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.statGrid}>
      {items.map((item, index) => (
        <StatCell key={`${item.label}-${index}`} label={item.label} value={item.value} />
      ))}
    </View>
  );
}

/** The "it's harder the further out" sentence, stated in the pick's own
 * numbers rather than as generic boilerplate — coridian_'s ask was
 * specifically that the horizon penalty be *visible*, not just applied. */
function horizonCopy(yearsOut: number | null, futureDiscount: number | null): string {
  if (yearsOut === null) {
    return 'Pick projections widen the further a draft sits in the future.';
  }
  if (yearsOut <= 0) {
    return "This class is already in view, so it takes no future discount — it's the most confidently projected pick horizon there is.";
  }
  const discountPct = futureDiscount === null ? null : Math.round((1 - futureDiscount) * 100);
  const drafts = yearsOut === 1 ? '1 draft' : `${yearsOut} drafts`;
  const discountClause = discountPct === null ? '' : ` and carries a ${discountPct}% future discount`;
  return `This pick is ${drafts} beyond the next class, so its owner's finish is that much less knowable: the projected slot range is wider, confidence is lower${discountClause}.`;
}

export default function PickDetailScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { pick, leagueId, leagueName } = route.params;

  useScreenHeaderTitle(navigation, pick.label ?? 'Draft Pick', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  const score = num(pick.score);
  const baseScore = num(pick.base_score);
  const yearsOut = num(pick.years_out);
  const futureDiscount = num(pick.future_discount);
  const confidence = num(pick.projection_confidence);
  const confidencePct = confidence === null ? null : confidence * 100;
  const identity = confidenceIdentity(confidence ?? 0, colors);
  const projectedSlot = num(pick.projected_slot_percentile);

  const bucketValues: Record<string, number | null> = {
    early: num(pick.early_probability),
    mid: num(pick.mid_probability),
    late: num(pick.late_probability),
  };
  const hasBuckets = buckets(colors).some((bucket) => bucketValues[bucket.key] !== null);
  // Every field below the headline is optional on the type (an older API
  // build predates them), so the whole breakdown collapses to one honest
  // notice rather than a grid of em-dashes.
  const hasBreakdown = baseScore !== null || futureDiscount !== null || confidence !== null;

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <View style={styles.header}>
          {/* Same icon-in-colored-disc landmark every other pick asset in the
              app uses (Trade Analyzer, Dashboard, recap trade detail) — the
              pick-side analog of Player Detail's round hero avatar. */}
          <IconCircle name="albums-outline" color={colors.accent} size={72} iconSize={32} />
          <AppText style={styles.heroTitle}>{pick.label ?? 'Draft pick'}</AppText>
          {pick.pick_tier ? (
            <View style={styles.heroPill}>
              <AppText style={styles.heroPillText}>{pick.pick_tier}</AppText>
            </View>
          ) : null}
          <AppText style={styles.heroScore}>{score === null ? '—' : Math.round(score)}</AppText>
          <AppText style={styles.heroScoreLabel}>Estimated value</AppText>
          {pick.projected_pick_range ? (
            <AppText style={styles.heroRange}>Projects as {pick.projected_pick_range}</AppText>
          ) : null}
        </View>

        <AnimatedCard style={styles.card}>
          <SectionHeading title="Snapshot" icon="flash-outline" />
          <StatGrid
            items={[
              { label: 'Draft year', value: pick.season },
              { label: 'Round', value: pick.round },
              { label: 'Drafts out', value: yearsOut },
              { label: 'Original team', value: pick.original_team_name },
              { label: 'Held by', value: pick.owner_team_name },
              { label: 'Projected range', value: pick.projected_pick_range },
            ]}
          />
        </AnimatedCard>

        {hasBreakdown ? (
          <>
            <AnimatedCard style={styles.card}>
              <SectionHeading title="Projected Range" icon="git-branch-outline" />
              <View style={styles.projectionTop}>
                <CircularProgressRing
                  percent={confidencePct ?? 0}
                  size={84}
                  color={identity.color}
                  label="Confidence"
                  valueLabel={confidencePct === null ? '—' : `${Math.round(confidencePct)}%`}
                />
                <View style={styles.projectionSummary}>
                  <AppText style={[styles.projectionVerdict, { color: identity.color }]}>
                    {identity.word} confidence
                  </AppText>
                  <AppText style={styles.projectionRange}>{pick.projected_pick_range ?? '—'}</AppText>
                  {projectedSlot !== null ? (
                    <AppText style={styles.projectionMeta}>
                      Projected slot percentile {Math.round(projectedSlot * 100)}
                      {' · higher = earlier in the round'}
                    </AppText>
                  ) : null}
                </View>
              </View>

              {hasBuckets ? (
                <View style={styles.buckets}>
                  <AppText style={styles.bucketsCaption}>Where this pick likely lands in its round</AppText>
                  {buckets(colors).map((bucket) => (
                    <BucketBar
                      key={bucket.key}
                      label={bucket.label}
                      percent={(bucketValues[bucket.key] ?? 0) * 100}
                      color={bucket.color}
                    />
                  ))}
                </View>
              ) : null}

              <View style={styles.horizonRow}>
                <Ionicons name="hourglass-outline" size={14} color={colors.textTertiary} />
                <AppText style={styles.horizonText}>{horizonCopy(yearsOut, futureDiscount)}</AppText>
              </View>
            </AnimatedCard>

            <AnimatedCard style={styles.card}>
              <SectionHeading title="Value Drivers" icon="analytics-outline" />
              <View style={styles.baseRow}>
                <AppText style={styles.baseLabel}>Base round value</AppText>
                <AppText style={styles.baseValue}>{baseScore === null ? '—' : Math.round(baseScore)}</AppText>
              </View>
              <MultiplierRow
                label="Future discount"
                multiplier={futureDiscount}
                note={
                  yearsOut === null || yearsOut <= 0
                    ? 'No horizon penalty — this class is already in view'
                    : `Compounds 12% per draft beyond the next class (${yearsOut} out)`
                }
              />
              <MultiplierRow
                label="Team strength"
                multiplier={num(pick.team_modifier)}
                note="Where the original team is projected to finish"
              />
              <MultiplierRow
                label="League format"
                multiplier={num(pick.format_multiplier)}
                note="Superflex / TE premium / league size adjustment"
              />
              <MultiplierRow
                label="Class strength"
                multiplier={num(pick.class_strength_multiplier)}
                note="How strong this draft class grades overall"
              />
              <MultiplierRow
                label="Prospect rankings"
                multiplier={num(pick.prospect_strength_multiplier)}
                note="Named prospects available in this range"
              />
              <View style={styles.resultRow}>
                <AppText style={styles.resultLabel}>Estimated value</AppText>
                <AppText style={styles.resultValue}>{score === null ? '—' : Math.round(score)}</AppText>
              </View>
            </AnimatedCard>
          </>
        ) : (
          <AppText style={styles.notice}>
            The valuation breakdown for this pick isn't available — update the app to see it.
          </AppText>
        )}
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  header: { alignItems: 'center', marginBottom: spacing.lg },
  heroTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  heroPill: {
    alignSelf: 'center',
    backgroundColor: colors.badgeBackground,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 3,
    marginTop: spacing.xs,
  },
  heroPillText: { fontSize: 11, fontWeight: '800', letterSpacing: 0.3, color: colors.badgeText },
  heroScore: { fontSize: 42, fontWeight: '800', color: colors.textPrimary, marginTop: spacing.md },
  heroScoreLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  heroRange: { fontSize: 12, color: colors.textSecondary, marginTop: spacing.sm },
  card: { padding: spacing.lg, marginBottom: spacing.sm },
  sectionHeadingRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.sm },
  sectionHeadingIcon: { marginRight: spacing.xs },
  // SectionHeading / StatGrid mirror Player Detail's (this is the pick-side
  // sibling of that screen), so the heading and tile styles match it too.
  sectionTitle: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  statCell: {
    minWidth: '46%',
    flexGrow: 1,
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  statCellLabel: {
    fontSize: 11,
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
    marginBottom: 2,
  },
  statCellValue: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
  projectionTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  projectionSummary: { flex: 1 },
  projectionVerdict: { fontSize: 15, fontWeight: '700' },
  projectionRange: { fontSize: 13, color: colors.textPrimary, marginTop: 2 },
  projectionMeta: { fontSize: 11, color: colors.textTertiary, marginTop: spacing.xs, lineHeight: 15 },
  buckets: { marginTop: spacing.lg },
  bucketsCaption: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: spacing.sm,
  },
  bucketRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.sm },
  bucketLabel: { width: 44, fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  bucketTrack: {
    flex: 1,
    height: 8,
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    overflow: 'hidden',
  },
  bucketFill: { height: '100%', borderRadius: radii.pill },
  bucketPercent: {
    width: 40,
    textAlign: 'right',
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  horizonRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  horizonText: { flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 17 },
  baseRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: spacing.sm,
    marginBottom: spacing.xs,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  baseLabel: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  baseValue: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
  driverRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing.sm },
  driverText: { flex: 1, paddingRight: spacing.sm },
  driverLabel: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  driverNote: { fontSize: 11, color: colors.textTertiary, marginTop: 2, lineHeight: 15 },
  driverValueBlock: { alignItems: 'flex-end', minWidth: 60 },
  driverValue: { fontSize: 15, fontWeight: '700' },
  driverDelta: { fontSize: 10, fontWeight: '700', marginTop: 1 },
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  resultLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  resultValue: { fontSize: 22, fontWeight: '800', color: colors.accent },
  notice: { fontSize: 13, color: colors.textSecondary, lineHeight: 19 },
  });
}
