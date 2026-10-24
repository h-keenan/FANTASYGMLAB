import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, TouchableOpacity, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import SectionHeading from './SectionHeading';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  EMPTY_START_HERE_STATE,
  START_HERE_STEPS,
  START_HERE_SUBTITLE,
  START_HERE_TITLE,
  markStartHereStepDone,
  parseStartHereState,
  shouldShowStartHere,
  startHereStorageKey,
  type StartHereRoute,
  type StartHereState,
} from '../lib/startHere';
import { thisWeekTarget } from '../lib/thisWeek';
import { spacing, type ThemeColors } from '../theme';

/**
 * First-run checklist for a newly created account (mirrors web-next's
 * StartHereCard): three destinations ticked when opened, dismissible.
 * Per-device state in AsyncStorage, only for accounts under
 * START_HERE_WINDOW_DAYS old.
 */
export default function StartHereCard({
  userId,
  accountCreatedAt,
  leagueId,
  leagueName,
  onNavigate,
}: {
  userId: string;
  accountCreatedAt: string | null | undefined;
  leagueId: string;
  leagueName: string;
  onNavigate: (name: string, params: object) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [state, setState] = useState<StartHereState | null>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(startHereStorageKey(userId))
      .then((raw) => {
        if (!cancelled) setState(parseStartHereState(raw));
      })
      .catch(() => {
        if (!cancelled) setState(EMPTY_START_HERE_STATE);
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (!state || !shouldShowStartHere(state, accountCreatedAt)) return null;

  const update = (next: StartHereState) => {
    setState(next);
    AsyncStorage.setItem(startHereStorageKey(userId), JSON.stringify(next)).catch(() => {});
  };

  return (
    <View style={styles.wrap}>
      <SectionHeading
        title={START_HERE_TITLE}
        right={
          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Hide the Start here checklist"
            onPress={() => update({ ...state, dismissed: true })}
            hitSlop={8}
            style={styles.hide}
          >
            <AppText style={styles.hideText}>Hide</AppText>
          </TouchableOpacity>
        }
      />
      <AccentCard accent={colors.accent} compact>
        <AppText style={styles.why}>{START_HERE_SUBTITLE}</AppText>
        {START_HERE_STEPS.map((step, index) => {
          const done = state.done.includes(step.key);
          return (
            <Pressable
              key={step.key}
              accessibilityRole="button"
              accessibilityLabel={`${step.label}${done ? ', done' : ''}`}
              onPress={() => {
                update(markStartHereStepDone(state, step.key));
                const target = thisWeekTarget(step.key as StartHereRoute, leagueId, leagueName);
                onNavigate(target.name, target.params);
              }}
              style={[styles.row, index > 0 ? styles.rowDivider : null]}
            >
              <AppText style={[styles.mark, { color: done ? colors.success : colors.textTertiary }]}>{done ? '✓' : '○'}</AppText>
              <View style={styles.rowText}>
                <AppText style={styles.headline}>{step.label}</AppText>
                <AppText style={styles.why}>{step.why}</AppText>
              </View>
              <AppText style={styles.arrow}>→</AppText>
            </Pressable>
          );
        })}
      </AccentCard>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm },
    hide: { minHeight: 44, justifyContent: 'center' },
    hideText: { fontSize: 13, fontWeight: '700', color: colors.textSecondary },
    headline: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    why: { fontSize: 13, color: colors.textSecondary },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingVertical: spacing.sm },
    rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    rowText: { flex: 1, minWidth: 0 },
    mark: { width: 20, fontSize: 16, fontWeight: '700' },
    arrow: { fontSize: 16, color: colors.accent },
  });
}
