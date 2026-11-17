import React, { useMemo, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PositionBadge from './PositionBadge';
import Tabs from './Tabs';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  teamSheetLevelLabel,
  teamSheetLevelTone,
  teamSheetPositionLine,
  teamSheetStreakTone,
  type TeamSheetChip,
  type TeamSheetPosition,
  type TeamSheetTile,
} from '../lib/teamSheet';
import { spacing, type ThemeColors } from '../theme';

/**
 * THE team sheet (header, Overview / Roster / Trades / History tabs, Overview tiles, streak line, strengths
 * and needs cards). The Fantasy Sim sheet and the Desk (real Sleeper) sheet both render through it and only
 * supply data and slots, so the two can never look different. Twin of web-next's TeamSheet.
 */

function toneColor(tone: string, colors: ThemeColors): string {
  switch (tone) {
    case 'success':
      return colors.success;
    case 'danger':
      return colors.danger;
    case 'accent':
      return colors.accent;
    case 'premium':
      return colors.premium;
    default:
      return colors.textSecondary;
  }
}

export interface TeamSheetTab {
  key: string;
  label: string;
  render: () => ReactNode;
}

export function TeamSheetFrame({
  id,
  logo,
  name,
  nameTestId,
  tag,
  chips,
  managedBy,
  managerIsAi = false,
  tabs,
}: {
  id: string;
  logo: ReactNode;
  name: string;
  nameTestId?: string;
  /** The trade-style tag slot (a badge, or the Free upsell). */
  tag?: ReactNode;
  chips: TeamSheetChip[];
  managedBy?: string | null;
  /** The manager is an AI: draws the small bot mark (lib/simManagerLabel.ts). */
  managerIsAi?: boolean;
  tabs: TeamSheetTab[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.stack}>
      <View style={styles.row}>
        {logo}
        <View style={styles.grow}>
          <AppText style={styles.title} testID={nameTestId}>
            {name}
          </AppText>
          <View style={styles.wrapRow}>
            {tag}
            {chips.map((c) => (
              <ToneBadge key={c.label} label={c.label} color={toneColor(c.tone, colors)} size="xs" />
            ))}
          </View>
          {managedBy ? (
            <View style={styles.managed} testID="team-sheet-manager">
              <AppText style={styles.muted}>Managed by {managedBy}</AppText>
              {managerIsAi ? <Ionicons name="hardware-chip-outline" size={14} color={colors.textTertiary} accessibilityLabel="AI manager" /> : null}
            </View>
          ) : null}
        </View>
      </View>
      <Tabs id={id} tabs={tabs} />
    </View>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.fact}>
      <AppText style={styles.factLabel}>{label}</AppText>
      <AppText style={styles.factValue}>{value}</AppText>
    </View>
  );
}

/** The Overview tab body: description, tiles, streak line, strengths and needs, injuries. Titles and injury rows are slots so each surface keeps its own heading and player-row look. */
export function TeamSheetOverview({
  blurb,
  tiles,
  streak,
  nextGame,
  positions,
  strengthsTitle,
  injuries,
}: {
  blurb?: ReactNode;
  tiles: TeamSheetTile[];
  streak?: string | null;
  nextGame?: string;
  positions: TeamSheetPosition[];
  strengthsTitle: ReactNode;
  injuries?: ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <>
      {blurb ? typeof blurb === 'string' ? <AppText style={styles.small}>{blurb}</AppText> : blurb : null}
      <View style={styles.facts} accessibilityLabel="Season so far">
        {tiles.map((t) => (
          <Tile key={t.label} label={t.label} value={t.value} />
        ))}
      </View>
      {streak || nextGame ? (
        <AppText style={styles.small}>
          {streak ? (
            <AppText style={{ fontWeight: '800', color: toneColor(teamSheetStreakTone(streak), colors) }}>Streak {streak}</AppText>
          ) : null}
          {streak && nextGame ? ' · ' : ''}
          {nextGame ?? ''}
        </AppText>
      ) : null}
      {strengthsTitle}
      <View style={styles.grid}>
        {positions.map((p) => {
          const color = toneColor(teamSheetLevelTone(p.level), colors);
          return (
            <View key={p.pos} style={styles.gridCell}>
              <AccentCard accent={color} compact>
                <View style={{ gap: 4, alignItems: 'flex-start' }}>
                  <PositionBadge position={p.pos} />
                  <AppText style={{ fontSize: 12.5, fontWeight: '800', color }}>{teamSheetLevelLabel(p.level)}</AppText>
                </View>
                <AppText style={styles.small}>{teamSheetPositionLine(p)}</AppText>
              </AccentCard>
            </View>
          );
        })}
      </View>
      {injuries}
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.md },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    grow: { flex: 1, minWidth: 0, gap: 4 },
    wrapRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    title: { fontSize: 17, fontWeight: '800', color: colors.textPrimary },
    managed: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    muted: { fontSize: 13.5, color: colors.textSecondary },
    small: { fontSize: 14, color: colors.textSecondary },
    facts: { flexDirection: 'row', gap: spacing.sm },
    fact: { flex: 1, alignItems: 'center', paddingVertical: spacing.sm, borderRadius: 12, borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glassInset },
    factLabel: { fontSize: 12, color: colors.textTertiary },
    factValue: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    gridCell: { flexBasis: '31%', flexGrow: 1 },
  });
}
