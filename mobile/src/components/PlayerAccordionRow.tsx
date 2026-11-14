import React, { useCallback, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import PlayerName from './PlayerName';
import PositionBadge from './PositionBadge';
import { PlayerBadges } from './PlayerBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { nextOpenId, playerRowModel, type FactTone, type PlayerFact, type PlayerFactsInput } from '../lib/playerAnatomy';
import type { BadgeInput } from '../lib/playerBadges';
import { radii, spacing, type ThemeColors } from '../theme';

function toneColor(tone: FactTone | undefined, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    case 'muted': return colors.textTertiary;
    default: return colors.textPrimary;
  }
}

/** One open row at a time across a list. */
export function usePlayerAccordion() {
  const [openId, setOpenId] = useState<string | null>(null);
  const toggle = useCallback((id: string) => setOpenId((cur) => nextOpenId(cur, id)), []);
  return { openId, toggle, isOpen: (id: string) => openId === id };
}

export type PlayerAccordionRowProps = PlayerFactsInput & {
  open: boolean;
  onToggle: () => void;
  badges?: BadgeInput[];
  /** Replaces the position pill text (a lineup slot such as "FLEX"). */
  positionLabel?: string | null;
  /** The ONE primary action of the expanded tile (the only gold/primary control). */
  primaryAction?: ReactNode;
  onOpenProfile?: () => void;
  children?: ReactNode;
  testID?: string;
};

/**
 * THE player row, native twin of web-next/src/components/ui/PlayerAccordionRow.tsx (logic: lib/playerAnatomy.ts).
 * Compact: avatar, name + position badge, TEAM · age · bye, one trailing key number or letter grade (no chevron: the
 * whole row is the tap target). Tapped it swells in place into a glass tile with the facts and the actions.
 * `mode="sim"` shows grade / ADP / projection, never OVR or trade value.
 */
export default function PlayerAccordionRow({ open, onToggle, badges = [], positionLabel, primaryAction, onOpenProfile, children, testID = 'player-accordion-row', ...input }: PlayerAccordionRowProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { player } = input;
  const model = playerRowModel(input);
  return (
    <View style={open ? styles.tile : styles.row} testID={testID}>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={`${player.name}, ${open ? 'hide' : 'show'} details`} onPress={onToggle} style={styles.head}>
        <PlayerAvatarSlot player={player} tier="row" />
        <View style={styles.main}>
          <View style={styles.line}>
            <PlayerName name={player.name} style={styles.name} />
            <PositionBadge position={player.position} label={positionLabel ?? undefined} />
            <PlayerBadges badges={badges} />
          </View>
          {model.meta.length > 0 ? <AppText style={styles.meta}>{model.meta.join(' · ')}</AppText> : null}
        </View>
        {model.trailing ? (
          <View style={styles.trailing}>
            <AppText style={[styles.trailingValue, { color: toneColor(model.trailing.tone, colors) }]}>{model.trailing.value}</AppText>
            <AppText style={styles.label}>{model.trailing.label}</AppText>
          </View>
        ) : null}
      </Pressable>
      {open ? (
        <View style={styles.body}>
          {model.facts.length > 0 ? (
            <View style={styles.facts}>
              {model.facts.map((fact: PlayerFact) => (
                <View key={fact.key} style={styles.fact}>
                  <AppText style={styles.label}>{fact.label}</AppText>
                  <AppText style={[styles.factValue, { color: toneColor(fact.tone, colors) }]}>{fact.value}</AppText>
                </View>
              ))}
            </View>
          ) : null}
          {children}
          {primaryAction || onOpenProfile ? (
            <View style={styles.actions}>
              {primaryAction}
              {onOpenProfile ? (
                <Pressable accessibilityRole="button" onPress={onOpenProfile} style={styles.secondary}>
                  <AppText style={styles.secondaryText}>Open profile</AppText>
                </Pressable>
              ) : null}
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { paddingHorizontal: spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    tile: { paddingHorizontal: spacing.sm, paddingBottom: spacing.md, marginVertical: spacing.xs, backgroundColor: colors.glass, borderWidth: 1, borderColor: colors.accent, borderRadius: radii.tile },
    head: { minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    main: { flex: 1, minWidth: 0 },
    line: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
    name: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    meta: { fontSize: 12, color: colors.textTertiary },
    trailing: { alignItems: 'flex-end' },
    trailingValue: { fontSize: 16, fontWeight: '800' },
    label: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
    body: { gap: spacing.sm, paddingTop: spacing.xs },
    facts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.lg },
    fact: { minWidth: 56 },
    factValue: { fontSize: 14, fontWeight: '800' },
    actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
    secondary: { minHeight: 44, paddingHorizontal: spacing.md, justifyContent: 'center', borderWidth: 1, borderColor: colors.borderStrong, borderRadius: radii.input },
    secondaryText: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  });
}
