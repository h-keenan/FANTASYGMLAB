import React, { useCallback, useMemo, useState, type ReactNode } from 'react';
import { AccessibilityInfo, LayoutAnimation, Platform, Pressable, StyleSheet, UIManager, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import PlayerName from './PlayerName';
import PositionBadge from './PositionBadge';
import { LetterGrade } from './LetterGrade';
import { PlayerBadges } from './PlayerBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { nextOpenId, playerRowModel, type FactTone, type PlayerFact, type PlayerFactsInput } from '../lib/playerAnatomy';
import type { BadgeInput } from '../lib/playerBadges';
import type { SimGradeInput } from '../lib/simGrade';
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
  /** Sim: the letter grade, a small tile at the end of the stats line (never a "GRADE" word or the trailing slot). */
  gradeTile?: SimGradeInput | null;
  /** Replaces the TEAM · Age · Bye line (caller's parts with the bye-soon tone and PROJ); one line, truncated. */
  metaParts?: { key: string; text: string; tone?: FactTone }[];
  /** Drop the position pill when a slot label column already says it. */
  hidePosition?: boolean;
  /** THE one trailing control (the sim's Move button): a sibling of the row Pressable, never nested in it. */
  trailingAction?: ReactNode;
};

let reduceMotion = false;
try {
  void Promise.resolve(AccessibilityInfo.isReduceMotionEnabled?.()).then((v) => { reduceMotion = Boolean(v); }).catch(() => {});
} catch {
  /* keep the animation */
}
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) UIManager.setLayoutAnimationEnabledExperimental(true);

/** Animate the next layout change (a row growing into its tile or collapsing) unless the person asked for reduced motion. */
export function animateRowExpand() {
  if (!reduceMotion) LayoutAnimation.configureNext(LayoutAnimation.create(180, LayoutAnimation.Types.easeInEaseOut, LayoutAnimation.Properties.opacity));
}

/**
 * THE player row, native twin of web-next/src/components/ui/PlayerAccordionRow.tsx (logic: lib/playerAnatomy.ts).
 * Compact: avatar, name + position badge, TEAM · age · bye, one trailing key number or letter grade (no chevron: the
 * whole row is the tap target). Tapped it swells in place into a glass tile with the facts and the actions.
 * `mode="sim"` shows grade / ADP / projection, never OVR or trade value.
 */
export default function PlayerAccordionRow({ open, onToggle, badges = [], positionLabel, primaryAction, onOpenProfile, children, testID = 'player-accordion-row', gradeTile, metaParts, hidePosition = false, trailingAction, ...input }: PlayerAccordionRowProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { player } = input;
  const model = playerRowModel(input);
  const metaLine: { key: string; text: string; tone?: FactTone }[] = metaParts ?? model.meta.map((text, i) => ({ key: `m${i}`, text }));
  const toggle = () => {
    animateRowExpand();
    onToggle();
  };
  return (
    <View style={open ? styles.tile : styles.row} testID={testID}>
      <View style={styles.headRow}>
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={`${player.name}, ${open ? 'hide' : 'show'} details`} onPress={toggle} style={styles.head}>
          <PlayerAvatarSlot player={player} tier="row" />
          <View style={styles.main}>
            <View style={styles.line}>
              <PlayerName name={player.name} style={styles.name} />
              {hidePosition ? null : <PositionBadge position={player.position} label={positionLabel ?? undefined} />}
              <PlayerBadges badges={badges} />
            </View>
            {metaLine.length > 0 || gradeTile ? (
              <View style={styles.metaRow} testID="row-meta">
                <AppText style={styles.meta} numberOfLines={1}>
                  {metaLine.map((part, i) => (
                    <AppText key={part.key} style={[styles.meta, part.tone ? { color: toneColor(part.tone, colors) } : null, part.tone === 'warning' || part.key === 'proj' ? { fontWeight: '700' } : null]}>
                      {i > 0 ? ' · ' : ''}
                      {part.text}
                    </AppText>
                  ))}
                </AppText>
                {gradeTile ? <LetterGrade grade={gradeTile} size="xs" testID="row-grade" /> : null}
              </View>
            ) : null}
          </View>
          {model.trailing && input.mode !== 'sim' ? (
            <View style={styles.trailing}>
              <AppText style={[styles.trailingValue, { color: toneColor(model.trailing.tone, colors) }]}>{model.trailing.value}</AppText>
              <AppText style={styles.label}>{model.trailing.label}</AppText>
            </View>
          ) : null}
        </Pressable>
        {trailingAction ? <View style={styles.action} testID="row-action">{trailingAction}</View> : null}
      </View>
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
    headRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    head: { flex: 1, minWidth: 0, minHeight: 52, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    action: { flexShrink: 0 },
    main: { flex: 1, minWidth: 0 },
    line: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
    name: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    meta: { fontSize: 12, color: colors.textTertiary, flexShrink: 1 },
    trailing: { alignItems: 'flex-end' },
    trailingValue: { fontSize: 16, fontWeight: '800' },
    label: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
    body: { gap: spacing.sm, paddingTop: spacing.xs },
    facts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.lg },
    fact: { minWidth: 56 },
    factValue: { fontSize: 14, fontWeight: '800' },
    actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
    secondary: { minHeight: 44, paddingHorizontal: spacing.md, justifyContent: 'center', borderWidth: 1, borderColor: colors.borderStrong, borderRadius: radii.input },
    secondaryText: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  });
}
