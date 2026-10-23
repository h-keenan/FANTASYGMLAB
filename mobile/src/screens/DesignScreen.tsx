import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Switch, TextInput, View } from 'react-native';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AppText from '../components/AppText';
import Button from '../components/Button';
import CircularProgressRing from '../components/CircularProgressRing';
import DashboardStatRow from '../components/DashboardStatRow';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GlassPanel from '../components/GlassPanel';
import GridBackground from '../components/GridBackground';
import MeterRow from '../components/ConfidenceMeter';
import MetricCard from '../components/MetricCard';
import NewBadge from '../components/NewBadge';
import PickPlate from '../components/PickPlate';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import PositionBadge from '../components/PositionBadge';
import PremiumLock from '../components/PremiumLock';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import SkeletonBlock, { SkeletonCard, SkeletonRows } from '../components/SkeletonBlock';
import StatStrip from '../components/StatStrip';
import ToneBadge from '../components/ToneBadge';
import TradeValueBar from '../components/TradeValueBar';
import ValueStat from '../components/ValueStat';
import { SheetHandle } from '../components/SwipeDismissSheet';
import { useThemeMode, type ThemeMode } from '../context/ThemeModeContext';
import { useOrbClearance } from '../lib/orbLayout';
import { radii, scrim, spacing, typography, type ThemeColors } from '../theme';

/**
 * Hidden design-system reference (mobile counterpart of web-next's /design).
 * Reachable only by long-pressing the "Legal" heading on the More screen; not
 * in any nav. Same family order as web. Every specimen is the real shared
 * component with static sample data and no network calls.
 */

const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB', 'FLEX', 'SUPER_FLEX', 'IDP_FLEX', 'BN', 'IR'];
const noop = () => {};

function Family({ title, note, styles, children }: { title: string; note: string; styles: ReturnType<typeof createStyles>; children: React.ReactNode }) {
  return (
    <View style={styles.family}>
      <AppText style={styles.familyTitle}>{title}</AppText>
      <AppText style={styles.note}>{note}</AppText>
      {children}
    </View>
  );
}

function Spec({
  name,
  path,
  duplicate,
  styles,
  children,
}: {
  name: string;
  path: string;
  duplicate?: string;
  styles: ReturnType<typeof createStyles>;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.spec}>
      <View style={styles.specHead}>
        <AppText style={styles.specName}>{name}</AppText>
        {duplicate ? (
          <View style={styles.dupFlag}>
            <AppText style={styles.dupFlagText}>DUPLICATE</AppText>
          </View>
        ) : null}
      </View>
      <AppText style={styles.path}>{path}</AppText>
      {duplicate ? <AppText style={styles.dupNote}>{duplicate}</AppText> : null}
      <View style={styles.specBody}>{children}</View>
    </View>
  );
}

export default function DesignScreen() {
  const { colors, mode, setMode } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const headerHeight = useHeaderHeight();
  const orbClearance = useOrbClearance();
  const [tab, setTab] = useState<'a' | 'b' | 'c'>('b');
  const [toggle, setToggle] = useState(true);

  return (
    <>
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingTop: headerHeight + spacing.md, paddingBottom: orbClearance }]}
      >
        <AppText style={styles.pageTitle}>Design system reference</AppText>
        <AppText style={styles.note}>
          Real shared components with static sample data. Request changes by component name. DUPLICATE marks near-copies to consolidate.
        </AppText>
        <SegmentedTabBar<ThemeMode>
          options={[
            { key: 'dark', label: 'Night' },
            { key: 'light', label: 'Day' },
            { key: 'auto', label: 'Auto' },
          ]}
          active={mode}
          onChange={setMode}
        />

        <Family styles={styles} title="Typography & tokens" note="Tokens live in mobile/src/theme.ts (colors, spacing, radii, typography).">
          <Spec styles={styles} name="typography scale" path="mobile/src/theme.ts (typography)">
            {Object.entries(typography).map(([key, value]) => (
              <AppText key={key} style={[value, { color: colors.textPrimary }]}>
                {key} {value.fontSize}/{value.fontWeight}
              </AppText>
            ))}
          </Spec>
          <Spec styles={styles} name="semantic colors" path="mobile/src/theme.ts (darkColors / lightColors)">
            <View style={styles.swatchGrid}>
              {(
                [
                  ['accent', colors.accent],
                  ['success', colors.success],
                  ['violet / diagnostic', colors.violet],
                  ['danger', colors.danger],
                  ['premium', colors.premium],
                  ['textPrimary', colors.textPrimary],
                  ['textSecondary', colors.textSecondary],
                  ['surface', colors.surface],
                  ['border', colors.cardBorder],
                  ['scrim', scrim],
                ] as Array<[string, string]>
              ).map(([name, color]) => (
                <View key={name} style={styles.swatchCell}>
                  <View style={[styles.swatch, { backgroundColor: color }]} />
                  <AppText style={styles.swatchLabel}>{name}</AppText>
                </View>
              ))}
            </View>
          </Spec>
          <Spec styles={styles} name="radii and spacing" path="mobile/src/theme.ts (radii, spacing)">
            <View style={styles.row}>
              {Object.entries(radii).map(([key, value]) => (
                <View key={key} style={{ alignItems: 'center', gap: 4 }}>
                  <View style={[styles.radiusBox, { borderRadius: Math.min(value, 24) }]} />
                  <AppText style={styles.swatchLabel}>{key} {value}</AppText>
                </View>
              ))}
            </View>
            {Object.entries(spacing).map(([key, value]) => (
              <View key={key} style={styles.row}>
                <AppText style={[styles.swatchLabel, { width: 36 }]}>{key}</AppText>
                <View style={{ width: value, height: 10, backgroundColor: colors.accent }} />
              </View>
            ))}
          </Spec>
          <Spec styles={styles} name="tap target" path="min 44pt (Button, rows)">
            <View style={styles.tapBox}>
              <AppText style={styles.swatchLabel}>44</AppText>
            </View>
          </Spec>
        </Family>

        <Family styles={styles} title="Buttons" note="One Button: primary / secondary / ghost, with disabled and loading.">
          <Spec styles={styles} name="Button" path="mobile/src/components/Button.tsx">
            <Button label="Primary" onPress={noop} />
            <Button label="Secondary" variant="secondary" onPress={noop} />
            <Button label="Ghost" variant="ghost" onPress={noop} />
            <Button label="Disabled" disabled onPress={noop} />
            <Button label="Loading" loading onPress={noop} />
          </Spec>
          <Spec
            styles={styles}
            name="Button vs EmptyState action button"
            path="components/Button.tsx | components/EmptyState.tsx"
            duplicate="EmptyState hand-rolls its own pill accent button (radii.pill, 13pt) instead of Button (radii.md, 15pt)."
          >
            <EmptyState icon="people-outline" title="Pill action inside EmptyState" actionLabel="Connect league" onPressAction={noop} />
          </Spec>
        </Family>

        <Family styles={styles} title="Badges & chips" note="Rounded pills; position badge has fixed per-position tints.">
          <Spec styles={styles} name="PositionBadge" path="mobile/src/components/PositionBadge.tsx">
            <View style={styles.wrap}>
              {POSITIONS.map((p) => (
                <PositionBadge key={p} position={p} />
              ))}
            </View>
            <View style={styles.wrap}>
              {['QB', 'RB', 'WR', 'TE'].map((p) => (
                <PositionBadge key={p} position={p} size="md" rank={12} />
              ))}
            </View>
          </Spec>
          <Spec
            styles={styles}
            name="ToneBadge vs NewBadge vs PositionBadge"
            path="components/ToneBadge.tsx | components/NewBadge.tsx | components/PositionBadge.tsx"
            duplicate="Several pill dialects (ToneBadge 10pt alpha tint, PositionBadge 20pt bordered, NewBadge). Also local TradeHubScreen CategoryBadge/ImpactBadge and TierBadge/UsageTrendPill/OverallRatingBadge."
          >
            <View style={styles.wrap}>
              <ToneBadge label="Starter" color={colors.success} />
              <ToneBadge label="Bench" color={colors.violet} />
              <ToneBadge label="Risk" color={colors.danger} />
              <ToneBadge label="Premium" color={colors.premium} />
              <NewBadge />
            </View>
          </Spec>
          <Spec
            styles={styles}
            name="SegmentedTabBar"
            path="mobile/src/components/SegmentedTabBar.tsx"
            duplicate="Web has three tab-bar implementations (PillRow x2, TradesTabBar); mobile has SegmentedTabBar plus ViewModeToggle, FilterDropdownButton and LeagueTypeControl."
          >
            <SegmentedTabBar<'a' | 'b' | 'c'>
              options={[
                { key: 'a', label: 'All' },
                { key: 'b', label: 'Starters' },
                { key: 'c', label: 'Bench' },
              ]}
              active={tab}
              onChange={setTab}
            />
          </Spec>
          <Spec styles={styles} name="ScreenInfoNote" path="mobile/src/components/ScreenInfoNote.tsx">
            <ScreenInfoNote label="How is this calculated?" text="Static sample explanation text for the info note." />
          </Spec>
        </Family>

        <Family styles={styles} title="Rows & lists" note="Player rows use PlayerIdentityRow; pick rows use PickPlate.">
          <Spec styles={styles} name="PlayerIdentityRow" path="mobile/src/components/PlayerIdentityRow.tsx">
            <PlayerIdentityRow
              playerId={null}
              name="Jaxon Smith-Njigba"
              position="WR"
              team="SEA"
              tier="elite"
              overallRating={91}
              trailingValue="8,120"
              trailingCaption="Value"
              showDivider
            />
            <PlayerIdentityRow
              playerId={null}
              name="Christian McCaffrey"
              position="RB"
              team="SF"
              tier="starter"
              injuryLabel="Q"
              trailingValue="4,310"
              trailingCaption="Value"
              showDivider
            />
            <PlayerIdentityRow playerId={null} name="Bench Guy" position="TE" team="DEN" tier="contributor" trailingValue="900" trailingCaption="Value" />
          </Spec>
          <Spec
            styles={styles}
            name="DraftPickAssetRow / PickPlate"
            path="components/DraftPickAssetRow.tsx | components/PickPlate.tsx"
            duplicate="Dashboard TradeAssetRow and Trade Finder/Hub ExchangeAssetList render picks themselves instead of DraftPickAssetRow."
          >
            <DraftPickAssetRow round={1} pickNo={3} label="2027 1st" projectedRange="Early 1st" trailingValue="5,200" trailingCaption="Value" showDivider />
            <View style={styles.row}>
              <PickPlate round={1} pickNo={3} />
              <PickPlate round={2} />
              <PickPlate />
            </View>
          </Spec>
          <Spec styles={styles} name="ValueStat" path="mobile/src/components/ValueStat.tsx">
            <ValueStat value={8120} />
          </Spec>
        </Family>

        <Family styles={styles} title="Cards" note="AccentCard has the semantic left rail; GlassPanel is for one-off heroes.">
          <Spec styles={styles} name="AccentCard" path="mobile/src/components/AccentCard.tsx">
            <AccentCard accent={colors.success}>
              <AppText style={styles.body}>Standard accent card (success)</AppText>
            </AccentCard>
            <AccentCard accent={colors.premium} compact>
              <AppText style={styles.body}>Compact accent card (warning)</AppText>
            </AccentCard>
          </Spec>
          <Spec styles={styles} name="GlassPanel" path="mobile/src/components/GlassPanel.tsx">
            <GlassPanel style={{ padding: spacing.lg }}>
              <AppText style={styles.body}>Glass panel surface</AppText>
            </GlassPanel>
          </Spec>
          <Spec
            styles={styles}
            name="PremiumLock vs AccentCard"
            path="components/PremiumLock.tsx | components/AccentCard.tsx"
            duplicate="PremiumLock is its own card treatment (tapping opens Paywall) rather than an AccentCard in the premium lane."
          >
            <PremiumLock title="Unlock Trade Finder" description="Static sample copy for the lock card." feature="design_sample" />
          </Spec>
          <Spec
            styles={styles}
            name="EmptyState vs ErrorState"
            path="components/EmptyState.tsx | components/ErrorState.tsx"
            duplicate="Same centered icon-circle layout in two files with different action buttons (pill accent vs Button secondary)."
          >
            <EmptyState icon="people-outline" title="Nothing here yet" subtitle="Add a league to see your team." actionLabel="Connect league" onPressAction={noop} />
          </Spec>
        </Family>

        <Family styles={styles} title="Stat tiles & meters" note="Tiles show a number; meters show a magnitude.">
          <Spec
            styles={styles}
            name="DashboardStatRow vs StatStrip vs MetricCard"
            path="components/DashboardStatRow.tsx | components/StatStrip.tsx | components/MetricCard.tsx"
            duplicate="Three stat-tile dialects (web has StatStrip/SnapshotTile and ValueStat)."
          >
            <DashboardStatRow
              items={[
                { label: 'Record', icon: 'trophy-outline', value: '8-4' },
                { label: 'Power', icon: 'flash-outline', value: '#2', valueColor: colors.success },
                { label: 'Franchise', icon: 'star-outline', value: '#1', valueColor: colors.premium },
                { label: 'Avg Age', icon: 'time-outline', value: '26.4' },
              ]}
            />
            <StatStrip
              items={[
                { label: 'Starters', value: '#3', tone: 'positive' },
                { label: 'Bench', value: '#9' },
                { label: 'Injuries', value: '2', tone: 'risk' },
              ]}
            />
            <MetricCard label="Record" value="8-4" note="Second best in the league" />
          </Spec>
          <Spec
            styles={styles}
            name="MeterRow vs CircularProgressRing"
            path="components/ConfidenceMeter.tsx | components/CircularProgressRing.tsx"
            duplicate="Confidence drawn as a segment meter and as a ring."
          >
            <MeterRow label="Confidence" value="High" level={3} color={colors.success} />
            <MeterRow label="Confidence" value="Low" level={1} color={colors.danger} />
            <View style={styles.row}>
              <CircularProgressRing percent={22} label="LOW" />
              <CircularProgressRing percent={88} label="HIGH" />
            </View>
          </Spec>
          <Spec styles={styles} name="TradeValueBar (win-prob / value edge)" path="mobile/src/components/TradeValueBar.tsx">
            <TradeValueBar delta={1500} />
            <TradeValueBar delta={0} />
            <TradeValueBar delta={-1800} />
          </Spec>
        </Family>

        <Family styles={styles} title="Headers" note="Section titles are uppercase; the header league switcher is part of the navigator header.">
          <Spec styles={styles} name="SectionHeading" path="mobile/src/components/SectionHeading.tsx">
            <SectionHeading title="Team Snapshot" />
            <SectionHeading title="Watchlist" caption="Sample caption" right={<AppText style={styles.link}>View all</AppText>} />
          </Spec>
          <Spec styles={styles} name="LeagueSwitcherHeaderButton" path="mobile/src/components/LeagueSwitcherHeaderButton.tsx">
            <AppText style={styles.note}>Lives in the navigator header (context-bound); see any league screen.</AppText>
          </Spec>
        </Family>

        <Family styles={styles} title="Sheets & overlays" note="Static previews; real sheets open from taps.">
          <Spec
            styles={styles}
            name="Sheet shell + scrim"
            path="components/SwipeDismissSheet.tsx (SheetHandle) | theme.ts (scrim)"
            duplicate="Several screens re-declare their own modal card (More guest-upgrade, Home rename) next to SwipeDismissCard."
          >
            <View style={{ backgroundColor: scrim, padding: spacing.lg, borderRadius: radii.md }}>
              <View style={styles.sheetPreview}>
                <SheetHandle />
                <AppText style={styles.body}>Sheet content preview</AppText>
              </View>
            </View>
          </Spec>
        </Family>

        <Family styles={styles} title="Forms" note="No shared Input component: inputs are styled per screen.">
          <Spec
            styles={styles}
            name="TextInput / Switch"
            path="inline per screen (More, Home, Login)"
            duplicate="Each form restyles TextInput (border/radii.input/colors.surface); no shared Input or Toggle."
          >
            <TextInput style={styles.input} placeholder="Sleeper username" placeholderTextColor={colors.textSecondary} />
            <View style={styles.row}>
              <Switch value={toggle} onValueChange={setToggle} />
              <AppText style={styles.body}>Share to community</AppText>
            </View>
          </Spec>
        </Family>

        <Family styles={styles} title="States" note="Loading skeletons, error, empty.">
          <Spec styles={styles} name="Skeletons" path="mobile/src/components/SkeletonBlock.tsx">
            <SkeletonBlock width="60%" height={16} />
            <SkeletonCard rows={2} />
            <SkeletonRows count={2} />
          </Spec>
          <Spec styles={styles} name="ErrorState" path="mobile/src/components/ErrorState.tsx">
            <ErrorState message="We could not load your league." onRetry={noop} />
          </Spec>
          <Spec styles={styles} name="EmptyState" path="mobile/src/components/EmptyState.tsx">
            <EmptyState icon="file-tray-outline" title="No action available" subtitle="Title and subtitle only." />
          </Spec>
        </Family>
      </ScrollView>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1 },
    content: { paddingHorizontal: spacing.lg, gap: spacing.lg },
    pageTitle: { fontSize: 24, fontWeight: '900', color: colors.textPrimary },
    note: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    family: { gap: spacing.md, marginTop: spacing.lg },
    familyTitle: {
      fontSize: 20,
      fontWeight: '900',
      letterSpacing: 1,
      textTransform: 'uppercase',
      color: colors.textPrimary,
      borderBottomWidth: 3,
      borderBottomColor: colors.accent,
      paddingBottom: spacing.xs,
    },
    spec: { gap: spacing.xs },
    specHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
    specName: { fontSize: 14, fontWeight: '800', color: colors.accent },
    path: { fontSize: 10, color: colors.textSecondary },
    specBody: { gap: spacing.sm, marginTop: spacing.xs },
    dupFlag: { backgroundColor: colors.premium, borderRadius: radii.pill, paddingHorizontal: 8, paddingVertical: 2 },
    dupFlagText: { fontSize: 10, fontWeight: '900', color: '#000' },
    dupNote: { fontSize: 12, color: colors.premium, lineHeight: 16 },
    body: { fontSize: 14, color: colors.textPrimary },
    link: { fontSize: 12, fontWeight: '700', color: colors.accent },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, flexWrap: 'wrap' },
    wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, alignItems: 'center' },
    swatchGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    swatchCell: { width: 72, gap: 2 },
    swatch: { height: 32, borderRadius: radii.sm, borderWidth: 1, borderColor: colors.cardBorder },
    swatchLabel: { fontSize: 10, color: colors.textSecondary },
    radiusBox: { width: 48, height: 36, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderStrong },
    tapBox: {
      width: 44,
      height: 44,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderStyle: 'dashed',
      borderColor: colors.accent,
    },
    sheetPreview: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
      gap: spacing.sm,
    },
    input: {
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderRadius: radii.input,
      paddingHorizontal: spacing.md,
      paddingVertical: 10,
      fontSize: 15,
      backgroundColor: colors.surface,
      color: colors.textPrimary,
    },
  });
}
