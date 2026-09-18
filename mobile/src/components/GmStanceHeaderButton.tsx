import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { TEAM_STRATEGY_OPTIONS } from '../lib/api';
import { useGmStance } from '../context/GmStanceContext';
import { colors, radii, spacing } from '../theme';

/**
 * A single header-mounted stance switcher, shared by every screen that
 * reads/writes GM Stance (League Overview, Trade Hub, Trade Analyzer) —
 * coridian_ asked for "one button in the header" instead of stance living
 * only as in-page pills on some screens and nowhere on others. Reads/writes
 * through GmStanceContext, so a change here is instantly visible on every
 * other screen already showing this league's stance.
 */
export default function GmStanceHeaderButton({ leagueId }: { leagueId: string }) {
  const { strategy, setStrategy } = useGmStance(leagueId);
  const [open, setOpen] = useState(false);
  const current = TEAM_STRATEGY_OPTIONS.find((option) => option.value === strategy);

  return (
    <>
      <TouchableOpacity style={styles.button} onPress={() => setOpen(true)} hitSlop={8}>
        <Text style={styles.buttonText} numberOfLines={1}>
          {current?.label ?? 'Stance'}
        </Text>
        <Ionicons name="chevron-down" size={12} color={colors.accent} />
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.title}>GM Stance</Text>
            <Text style={styles.subtitle}>How should this league's advice be framed?</Text>
            {TEAM_STRATEGY_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.value}
                style={styles.optionRow}
                onPress={() => {
                  setStrategy(option.value);
                  setOpen(false);
                }}
              >
                <Text style={[styles.optionText, option.value === strategy && styles.optionTextActive]}>
                  {option.label}
                </Text>
                {option.value === strategy ? (
                  <Ionicons name="checkmark-circle" size={18} color={colors.accent} />
                ) : null}
              </TouchableOpacity>
            ))}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
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
  buttonText: { fontSize: 12, fontWeight: '700', color: colors.accent, flexShrink: 1 },
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
  optionText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  optionTextActive: { color: colors.accent },
});
