import React, { useMemo, useState } from 'react';
import { Modal, Pressable, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import { Ionicons } from '@expo/vector-icons';

import { TEAM_STANCE_OPTIONS } from '../lib/api';
import { useGmStance } from '../context/GmStanceContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * A single header-mounted stance switcher, shared by every screen that
 * reads/writes Team Situation (League Overview, Trade Hub, Trade Analyzer)
 * — coridian_ asked for "one button in the header" instead of stance living
 * only as in-page pills on some screens and nowhere on others. Reads/writes
 * through GmStanceContext, so a change here is instantly visible on every
 * other screen already showing this league's stance.
 *
 * GM Stance / Team Situation merge (product decision, 2026-09-26): this
 * used to be a five-option "GM Stance" picker (Contender/Fringe
 * Contender/Retool/Rebuild/Tank) backed by its own now-retired storage.
 * It's now Team Situation's three-option picker (Rebuilding/Competing/
 * Balanced) — the SAME control TeamStanceScreen's dedicated "Team
 * Situation" screen offers — and it now genuinely drives real trade/lineup
 * valuation adjustments, not just rationale framing. Team Situation has no
 * "unset"/"Reset to Auto" concept, so that affordance is gone too: a
 * league with nothing declared just shows the Balanced fallback.
 *
 * The *only* stance control: the in-page pill rows some screens used to
 * carry were left behind when this was added, and each wrote to the same
 * shared context, so League Overview showed two live copies of the same
 * control at once ("glitchy" per coridian_'s screenshot).
 */
export default function GmStanceHeaderButton({ leagueId }: { leagueId: string }) {
  const { stance, isSet, setStance } = useGmStance(leagueId);
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const current = TEAM_STANCE_OPTIONS.find((option) => option.value === stance);

  return (
    <>
      <TouchableOpacity style={styles.button} onPress={() => setOpen(true)} hitSlop={8}>
        <AppText style={styles.buttonText} numberOfLines={1}>
          {isSet ? current?.label ?? 'Balanced' : 'Balanced'}
        </AppText>
        <Ionicons name="chevron-down" size={12} color={colors.accent} />
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <AppText style={styles.title}>Team Situation</AppText>
            <AppText style={styles.subtitle}>
              {isSet
                ? "How should this league's advice be framed? Remembered for this league — it shapes Trade Hub, Trade Analyzer, and Dashboard suggestions, plus trade and lineup value adjustments."
                : "Not set yet — we're reading this league as Balanced until you pick one."}
            </AppText>
            {TEAM_STANCE_OPTIONS.map((option) => {
              const active = isSet && option.value === stance;
              return (
                <TouchableOpacity
                  key={option.value}
                  style={styles.optionRow}
                  onPress={() => {
                    setStance(option.value);
                    setOpen(false);
                  }}
                >
                  <View style={styles.optionTextGroup}>
                    <AppText style={[styles.optionText, active && styles.optionTextActive]}>{option.label}</AppText>
                    <AppText style={styles.optionHint}>{option.description}</AppText>
                  </View>
                  {active ? <Ionicons name="checkmark-circle" size={18} color={colors.accent} /> : null}
                </TouchableOpacity>
              );
            })}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.accentMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
    maxWidth: 150,
  },
  // accentOnTint: sits on this button's own accentMuted fill, where plain
  // accent falls under AA on light mode (color-system audit, 2026-09-25).
  buttonText: { fontSize: 12, fontWeight: '700', color: colors.accentOnTint, flexShrink: 1 },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.backgroundElevated,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  subtitle: { fontSize: 13, color: colors.textSecondary, marginTop: 2, marginBottom: spacing.md },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  optionTextGroup: { flexShrink: 1, paddingRight: spacing.sm },
  optionText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  // accentOnTint: plain accent measures only 4.02:1 against this sheet's
  // backgroundElevated surface on light mode, under AA (color-system
  // audit, 2026-09-25).
  optionTextActive: { color: colors.accentOnTint },
  optionHint: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
  });
}
