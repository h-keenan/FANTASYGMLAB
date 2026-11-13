import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import MetricCard from './MetricCard';
import PercentileBar from './PercentileBar';
import { Section as PqvSection } from './PlayerQuickViewSheet';
import ToneBadge from './ToneBadge';
import WeeklyPointsChart from './WeeklyPointsChart';
import { useThemeMode } from '../context/ThemeModeContext';

import type { SimScoutingProfile } from '../lib/simGame';
import { simCollegeCaption, simCollegeTiles, simCurveBand, simCurveCaption, simDraftLine, simMeasurableTiles, simOrdinal, simTagConfidenceLabel } from '../lib/simScouting';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Generated-prospect sections of the Fantasy Sim player sheet (twin of web's SimScoutingSections): scouting
 * report, college production, measurables, analytics percentiles vs the position class and the development
 * curve, in the quick view's own section shell, tiles and chart. All of it is simulated and says so.
 */
export default function SimScoutingSections({ profile }: { profile: SimScoutingProfile }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const dev = profile.development;
  const real = profile.source !== 'generated';
  const chip = (text: string, key?: string) => (
    <View key={key ?? text} style={styles.chip}>
      <AppText style={styles.chipText}>{text}</AppText>
    </View>
  );
  return (
    <>
      <PqvSection title="Scouting report" right={<ToneBadge label={real ? 'Prospect' : profile.label} color={colors.accent} />}>
        <View style={styles.wrap} testID="sim-scouting-report">
          {chip(`${simDraftLine(profile.draft)} (proj.)`)}
          {chip(`Class rank #${profile.draft.class_rank} of ${profile.draft.class_size}`)}
          {profile.tags.map((t) => chip(`${t.tag} · ${simTagConfidenceLabel(t.confidence)}`, t.tag))}
        </View>
        <AppText style={styles.body}>{profile.blurb}</AppText>
      </PqvSection>
      <PqvSection title="College production">
        <AppText style={styles.muted}>{simCollegeCaption(profile.college)}</AppText>
        <View style={styles.tileGrid}>
          {simCollegeTiles(profile.college).map((t) => (
            <MetricCard key={t.label} label={t.label} value={t.value} percentile={t.percentile} />
          ))}
        </View>
      </PqvSection>
      <PqvSection title="Measurables">
        <View style={styles.tileGrid}>
          {simMeasurableTiles(profile).map((t) => (
            <MetricCard key={t.label} label={t.label} value={t.value} percentile={t.percentile} />
          ))}
        </View>
      </PqvSection>
      <PqvSection title="Analytics vs position class">
        <View style={styles.bars}>
          {profile.analytics.map((a) => (
            <View key={a.key} accessible accessibilityLabel={`${a.label} ${a.display}, ${simOrdinal(a.percentile)} percentile`}>
              <View style={styles.barHead}>
                <AppText style={styles.muted}>{a.label}</AppText>
                <AppText style={styles.strong}>
                  {a.display} · {simOrdinal(a.percentile)}
                </AppText>
              </View>
              <PercentileBar percentile={a.percentile} />
            </View>
          ))}
        </View>
      </PqvSection>
      {dev.points.length > 0 ? (
        <PqvSection
          title="Development curve"
          right={
            <ToneBadge
              label={dev.revealed && dev.archetype_label ? dev.archetype_label : `Scouting ${dev.confidence_label.toLowerCase()} confidence`}
              color={dev.revealed ? colors.success : colors.warning}
            />
          }
        >
          <WeeklyPointsChart weeks={[]} projection={simCurveBand(dev)} pointsLabel="ppg" xLabel="Year" />
          <AppText style={styles.muted}>
            <AppText style={styles.strong}>{simCurveCaption(dev)}</AppText> · {dev.note}
          </AppText>
        </PqvSection>
      ) : null}
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
    chip: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radii.pill,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
    },
    chipText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    body: { fontSize: 14, lineHeight: 20, color: colors.textSecondary },
    muted: { fontSize: 13, color: colors.textTertiary },
    strong: { fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    tileGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    bars: { gap: spacing.sm },
    barHead: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.sm },
  });
}
