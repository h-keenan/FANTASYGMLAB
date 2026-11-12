import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import PremiumLock from '../components/PremiumLock';
import SectionHeading from '../components/SectionHeading';
import { SkeletonCard } from '../components/SkeletonBlock';
import ToneBadge from '../components/ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import {
  SIM_DISCLAIMER,
  SIM_GAME_CARD,
  SIM_LABEL,
  isSimOffError,
  simFactorImpact,
  simFactorKindLabel,
  simFactorsIntro,
  simFinishRange,
  simFormatCurrent,
  simFormatPercent,
  simGate,
  simHeadline,
  simNoteMessages,
  simOddsTone,
  simOrdinal,
  simReasonMessage,
  simScopeLine,
  simUnavailableCopy,
  simWinsRange,
  type SimForecastResponse,
  type SimTone,
  type SimUnavailableCause,
  type SimUpsell,
} from '../lib/simPresentation';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'FantasySim'>;

type Phase =
  | { kind: 'loading' }
  | { kind: 'unavailable'; cause: SimUnavailableCause }
  | { kind: 'premium'; upsell: SimUpsell | null }
  | { kind: 'notice'; message: string }
  | { kind: 'ready'; data: SimForecastResponse }
  | { kind: 'error'; message: string };

function errorText(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const e = error as { status?: number; code?: string; message?: string };
    if (e.status === 503 || e.code === 'server_busy') return 'The forecast is busy right now. Try again in a few seconds.';
    if (e.message) return e.message;
  }
  return fallback;
}

export default function FantasySimScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  useScreenHeaderTitle(navigation, 'Season Outlook', leagueName);

  const toneColor = useCallback(
    (tone: SimTone) => ({ success: colors.success, accent: colors.accent, warning: colors.warning, danger: colors.danger })[tone],
    [colors],
  );

  const [phase, setPhase] = useState<Phase>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimForecast(leagueId)
      .then((data) => {
        if (cancelled) return;
        const gate = simGate(data);
        if (gate.kind === 'premium') return setPhase({ kind: 'premium', upsell: gate.upsell });
        if (gate.kind === 'unavailable') return setPhase({ kind: 'unavailable', cause: gate.cause });
        if (data.reason || !data.forecast) {
          return setPhase({ kind: 'notice', message: simReasonMessage(data.reason) || 'We could not build your forecast. Try again.' });
        }
        setPhase({ kind: 'ready', data });
      })
      .catch((error) => {
        if (cancelled) return;
        if (isSimOffError(error)) setPhase({ kind: 'unavailable', cause: 'off' });
        else setPhase({ kind: 'error', message: errorText(error, 'Could not build your season outlook.') });
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, attempt]);

  const refresh = () => {
    setPhase({ kind: 'loading' });
    setAttempt((n) => n + 1);
  };

  const shell = (children: React.ReactNode) => (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        {children}
      </ScrollView>
    </View>
  );

  const gameCard = (
    <AccentCard accent={colors.premium}>
      <SectionHeading title={SIM_GAME_CARD.title} caption={SIM_GAME_CARD.body} />
      <Button label={SIM_GAME_CARD.action} variant="secondary" onPress={() => navigation.navigate('GmGame')} />
    </AccentCard>
  );

  if (phase.kind === 'loading') {
    return shell(
      <View style={styles.stack}>
        <AppText style={styles.label} accessibilityLiveRegion="polite">
          Playing out the rest of your season…
        </AppText>
        <SkeletonCard rows={4} />
        <SkeletonCard rows={2} />
        <SkeletonCard rows={4} />
      </View>,
    );
  }
  if (phase.kind === 'error') {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState title="Couldn't load your season outlook" message={phase.message} onRetry={refresh} />
      </View>
    );
  }
  if (phase.kind === 'premium') {
    return shell(
      <PremiumLock
        feature="fantasy_sim"
        leagueName={leagueName}
        title={phase.upsell?.title || 'See your season forecast'}
        description={
          phase.upsell?.body ||
          'Season Outlook is a Pro feature in your GM Plan: one tap shows your playoff odds, projected record and finish, title odds, and the moves and games that swing your season. Start your free trial to unlock it.'
        }
      />,
    );
  }
  if (phase.kind === 'unavailable') {
    const copy = simUnavailableCopy();
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <EmptyState icon="flask-outline" title={copy.title} subtitle={copy.subtitle} />
      </View>
    );
  }
  if (phase.kind === 'notice') {
    return shell(
      <View style={styles.stack}>
        <AppText style={[styles.help, { color: colors.warning }]} accessibilityRole="alert">
          {phase.message}
        </AppText>
        <Button label="Try again" variant="secondary" onPress={refresh} />
        {gameCard}
      </View>,
    );
  }

  const { data } = phase;
  const forecast = data.forecast!;
  const tone = toneColor(simOddsTone(forecast.odds.playoffs));
  const noteLines = simNoteMessages(data.notes);
  const tiles: [string, string, string][] = [
    ['Playoff odds', simFormatPercent(forecast.odds.playoffs), `${forecast.odds.playoff_spots} teams make it`],
    ['Championship odds', simFormatPercent(forecast.odds.title), `Reach the final: ${simFormatPercent(forecast.odds.finals)}`],
    ['Projected record', forecast.record.projected, `Likely range: ${simWinsRange(forecast.record)}`],
    ['Projected finish', simOrdinal(forecast.finish.median), `Likely range: ${simFinishRange(forecast.finish)} of ${forecast.finish.teams}`],
  ];
  const peak = Math.max(0.01, ...forecast.finish.distribution.map((b) => b.probability));

  return shell(
    <View style={styles.stack}>
      <View style={styles.stackTight} accessibilityRole="summary">
        <View style={styles.banner}>
          <ToneBadge label={SIM_LABEL} color={colors.accent} size="xs" />
          <AppText style={[styles.help, styles.flex, styles.bold]}>{simScopeLine(forecast, data.mode, data.as_of)}</AppText>
        </View>
        <AppText style={styles.help}>{SIM_DISCLAIMER}</AppText>
      </View>

      <AccentCard accent={tone} glow>
        <View style={styles.row}>
          <View style={[styles.oddsCircle, { borderColor: tone }]} accessibilityLabel={`Playoff odds ${simFormatPercent(forecast.odds.playoffs)}`}>
            <AppText style={[styles.oddsText, { color: tone }]}>{simFormatPercent(forecast.odds.playoffs)}</AppText>
          </View>
          <View style={styles.flex}>
            <AppText style={styles.help}>{leagueName.toUpperCase()}</AppText>
            <AppText style={styles.title}>{forecast.team.name}</AppText>
            <AppText style={styles.help}>Now {simFormatCurrent(forecast.current)}</AppText>
          </View>
        </View>
        <AppText style={styles.label}>{simHeadline(forecast)}</AppText>
      </AccentCard>

      <View style={styles.grid}>
        {tiles.map(([label, value, sub]) => (
          <View key={label} style={styles.tile}>
            <AppText style={styles.help}>{label}</AppText>
            <AppText style={styles.title}>{value}</AppText>
            <AppText style={styles.help}>{sub}</AppText>
          </View>
        ))}
      </View>

      <SectionHeading title="Where you finish" caption="How often you land in each spot across the simulated seasons. Green spots make the playoffs." />
      <View style={styles.stackTight}>
        {forecast.finish.distribution.map((bucket) => {
          const inPlayoffs = bucket.finish <= forecast.odds.playoff_spots;
          return (
            <View key={bucket.finish} style={styles.row}>
              <AppText style={[styles.help, styles.rankCell]}>{simOrdinal(bucket.finish)}</AppText>
              <View style={[styles.barTrack, styles.flex]}>
                <View style={[styles.barFill, { width: `${(bucket.probability / peak) * 100}%`, backgroundColor: inPlayoffs ? colors.success : colors.borderStrong }]} />
              </View>
              <AppText style={[styles.help, styles.pctCell]}>{simFormatPercent(bucket.probability)}</AppText>
            </View>
          );
        })}
      </View>

      <SectionHeading title="What swings your season" caption={simFactorsIntro(forecast.swing_factors)} />
      {forecast.swing_factors.map((factor, index) => {
        const color = factor.playoff_delta >= 0 ? colors.success : colors.warning;
        return (
          <AccentCard key={`${factor.kind}-${index}`} accent={color} compact>
            <View style={styles.row}>
              <ToneBadge label={simFactorKindLabel(factor.kind)} color={color} size="xs" />
              <AppText style={[styles.help, styles.bold, styles.flex]}>{simFactorImpact(factor)}</AppText>
            </View>
            <AppText style={styles.label}>{factor.title}</AppText>
            <AppText style={styles.help}>{factor.detail}</AppText>
          </AccentCard>
        );
      })}

      {gameCard}

      <Button label="Refresh forecast" variant="ghost" onPress={refresh} />
      {noteLines.map((line) => (
        <AppText key={line} style={styles.help}>
          {line}
        </AppText>
      ))}
    </View>,
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background, padding: spacing.xl },
    stack: { gap: spacing.md },
    stackTight: { gap: spacing.xs },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    flex: { flex: 1, minWidth: 0 },
    banner: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    bold: { fontWeight: '700' },
    label: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    help: { fontSize: 13, lineHeight: 19, color: colors.textSecondary },
    title: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
    oddsCircle: { width: 88, height: 88, borderRadius: radii.pill, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
    oddsText: { fontSize: 24, fontWeight: '800' },
    barTrack: { height: 8, borderRadius: 4, backgroundColor: colors.surface, overflow: 'hidden' },
    barFill: { height: 8, borderRadius: 4 },
    rankCell: { width: 36 },
    pctCell: { width: 44, textAlign: 'right' },
    grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    tile: { flexBasis: '48%', flexGrow: 1, gap: spacing.xs, padding: spacing.md, borderRadius: radii.md, backgroundColor: colors.surface },
  });
}
