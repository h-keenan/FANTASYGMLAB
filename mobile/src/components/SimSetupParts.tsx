import React, { useMemo, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import AppText from './AppText';
import GlassCard from './GlassCard';
import { MotionIn } from './Motion';
import SimGlyph from './SimGlyph';
import Toggle from './Toggle';
import { useThemeMode } from '../context/ThemeModeContext';
import { SIM_DIFFICULTY_COPY, type SimDifficulty } from '../lib/simGame';
import { SIM_DIFFICULTY_CARDS, SIM_SETUP_CARDS, type SimSetupCardId } from '../lib/simSetupView';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Building blocks of the Fantasy Sim "New game" form (twin of web-next/src/components/SimSetupParts.tsx): glass section
 * cards with an icon, title and live one-line summary, labelled fields, switch rows inside a card, difficulty tiles and
 * the live "your league" summary. Shared GlassCard / MotionIn / Toggle and theme tokens only.
 */

function useStyles() {
  const { colors } = useThemeMode();
  return { colors, styles: useMemo(() => createStyles(colors), [colors]) };
}

export function SetupCard({ id, summary, index = 0, count = 1, children }: { id: SimSetupCardId; summary: string; index?: number; count?: number; children: ReactNode }) {
  const { colors, styles } = useStyles();
  const card = SIM_SETUP_CARDS[id];
  return (
    <MotionIn index={index} count={count}>
      <GlassCard style={styles.card} testID={`sim-setup-card-${id}`}>
        <View style={styles.cardHead}>
          <View style={styles.iconChip}>
            <SimGlyph name={card.glyph} color={colors.accent} size={18} />
          </View>
          <View style={styles.grow}>
            <AppText style={styles.cardTitle} accessibilityRole="header">{card.title}</AppText>
            <AppText style={styles.cardSummary} numberOfLines={1}>{summary}</AppText>
          </View>
        </View>
        {children}
      </GlassCard>
    </MotionIn>
  );
}

export function SetupField({ label, note, children }: { label: string; note?: string; children: ReactNode }) {
  const { styles } = useStyles();
  return (
    <View style={styles.field}>
      <AppText style={styles.fieldLabel}>{label}</AppText>
      {children}
      {note ? <AppText style={styles.help}>{note}</AppText> : null}
    </View>
  );
}

export function SetupNote({ children, testID }: { children: ReactNode; testID?: string }) {
  const { styles } = useStyles();
  return <AppText style={styles.help} testID={testID}>{children}</AppText>;
}

export function SetupToggleGroup({ children }: { children: ReactNode }) {
  const { styles } = useStyles();
  return <View style={styles.toggleGroup}>{children}</View>;
}

export function SetupToggleRow({ label, note, value, onChange, first = false }: { label: string; note: string; value: boolean; onChange: (next: boolean) => void; first?: boolean }) {
  const { styles } = useStyles();
  return (
    <View style={[styles.toggleRow, first ? null : styles.toggleDivider]}>
      <View style={styles.grow}>
        <AppText style={styles.fieldLabel}>{label}</AppText>
        <AppText style={styles.help}>{note}</AppText>
      </View>
      <Toggle value={value} onValueChange={onChange} label={label} />
    </View>
  );
}

export function DifficultyTiles({ values, active, onSelect }: { values: SimDifficulty[]; active: SimDifficulty; onSelect: (value: SimDifficulty) => void }) {
  const { colors, styles } = useStyles();
  return (
    <View style={styles.tiles} accessibilityRole="radiogroup" accessibilityLabel="Difficulty">
      {values.map((value) => {
        const on = value === active;
        return (
          <Pressable
            key={value}
            accessibilityRole="radio"
            accessibilityState={{ checked: on }}
            accessibilityLabel={`${SIM_DIFFICULTY_COPY[value].label}. ${SIM_DIFFICULTY_CARDS[value].detail}`}
            onPress={() => onSelect(value)}
            style={[styles.tile, on ? styles.tileOn : null]}
          >
            <View style={[styles.radio, on ? styles.radioOn : null]}>{on ? <SimGlyph name="check" color={colors.onAccent} size={12} /> : null}</View>
            <View style={styles.grow}>
              <AppText style={styles.fieldLabel}>
                {SIM_DIFFICULTY_COPY[value].label}
                <AppText style={[styles.tagline, on ? styles.taglineOn : null]}>{` · ${SIM_DIFFICULTY_CARDS[value].tagline}`}</AppText>
              </AppText>
              <AppText style={styles.help}>{SIM_DIFFICULTY_CARDS[value].detail}</AppText>
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

export function SetupSummaryCard({ headline, chips, detail }: { headline: string; chips: string[]; detail: string }) {
  const { styles } = useStyles();
  return (
    <MotionIn>
      <GlassCard style={[styles.card, styles.hero]} testID="sim-setup-hero">
        <AppText style={styles.kicker}>Your league</AppText>
        <AppText style={styles.headline} accessibilityLiveRegion="polite">{headline}</AppText>
        <View style={styles.chips}>
          {chips.map((chip) => (
            <View key={chip} style={styles.chip}>
              <AppText style={styles.chipText}>{chip}</AppText>
            </View>
          ))}
        </View>
        <AppText style={styles.help} testID="sim-setup-summary">{detail}</AppText>
      </GlassCard>
    </MotionIn>
  );
}

/** Pinned above the home indicator while the form scrolls. */
export function SetupStickyBar({ children, warning }: { children: ReactNode; warning?: string | null }) {
  const { styles } = useStyles();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, spacing.md) }]} testID="sim-setup-bar">
      {warning ? <AppText style={styles.warning}>{warning}</AppText> : null}
      <View style={styles.barRow}>{children}</View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    grow: { flex: 1, minWidth: 0 },
    card: { gap: spacing.lg },
    cardHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    iconChip: { width: 36, height: 36, borderRadius: radii.sm, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accentMuted, borderWidth: 1, borderColor: colors.accent },
    cardTitle: { fontSize: 16.5, fontWeight: '800', color: colors.textPrimary },
    cardSummary: { fontSize: 13, color: colors.accent },
    field: { gap: spacing.sm },
    fieldLabel: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    help: { fontSize: 13, lineHeight: 18, color: colors.textSecondary },
    toggleGroup: { borderRadius: radii.md, borderWidth: StyleSheet.hairlineWidth * 1.5, borderColor: colors.glassBorder, paddingHorizontal: spacing.md, backgroundColor: colors.accentMuted },
    toggleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md, paddingVertical: spacing.sm, minHeight: 56 },
    toggleDivider: { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopColor: colors.glassBorder },
    tiles: { gap: spacing.sm },
    tile: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, minHeight: 56, paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radii.md, borderWidth: 1, borderColor: colors.glassBorder },
    tileOn: { borderColor: colors.accent, backgroundColor: colors.accentMuted, shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 0 }, elevation: 3 },
    radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
    radioOn: { borderColor: colors.accent, backgroundColor: colors.accent },
    tagline: { fontSize: 14.5, fontWeight: '600', color: colors.textSecondary },
    taglineOn: { color: colors.accent },
    hero: { borderTopWidth: 3, borderTopColor: colors.accent, gap: spacing.md },
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.premium },
    headline: { fontSize: 18, lineHeight: 24, fontWeight: '800', color: colors.textPrimary },
    chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    chip: { paddingVertical: 4, paddingHorizontal: spacing.md, borderRadius: radii.pill, backgroundColor: colors.accentMuted, borderWidth: 1, borderColor: colors.accent },
    chipText: { fontSize: 13, fontWeight: '700', color: colors.accentOnTint },
    bar: { paddingTop: spacing.md, paddingHorizontal: spacing.lg, gap: spacing.sm, backgroundColor: colors.backgroundElevated, borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopColor: colors.glassBorder },
    barRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    warning: { fontSize: 13, color: colors.warning },
  });
}
