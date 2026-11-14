import React, { useEffect, useMemo, useReducer } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import { useGmStance } from '../context/GmStanceContext';
import { api, type TeamStance } from '../lib/api';
import {
  DIRECTION_CHECKIN_INITIAL,
  directionChangedMessage,
  directionCheckinReducer,
  directionSwitchLabel,
  type DirectionCheckinAction,
  type DirectionCheckinOption,
} from '../lib/directionCheckin';
import { spacing, type ThemeColors } from '../theme';

/**
 * Dashboard direction check-in (mirrors web-next's DirectionCheckinCard). A few
 * times a season (start of season, midseason, trade deadline, playoff push) the
 * server says whether to ask if the declared Team Situation still fits and
 * writes the words (lib/directionCheckin.ts, modules/direction_checkin.py).
 * Switching goes through GmStanceContext, the same optimistic Team Situation
 * write every other mobile screen uses, so the rest of the app updates at once.
 * Every answer, a dismissal included, ends that moment for the season: no nag
 * loop. Self-fetching and silent on any failure.
 */
export default function DirectionCheckinCard({ leagueId, onChanged }: { leagueId: string; onChanged?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [state, dispatch] = useReducer(directionCheckinReducer, DIRECTION_CHECKIN_INITIAL);
  const { setStance } = useGmStance(leagueId);

  useEffect(() => {
    let cancelled = false;
    api
      .getDirectionCheckin(leagueId)
      .then((response) => {
        if (!cancelled) dispatch({ type: 'loaded', response });
      })
      .catch(() => {
        if (!cancelled) dispatch({ type: 'loaded', response: null });
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (state.phase === 'changed') {
    return (
      <AccentCard accent={colors.accent} compact>
        <AppText style={styles.body} accessibilityRole="text">
          {directionChangedMessage(state.label)}
        </AppText>
      </AccentCard>
    );
  }
  if (state.phase !== 'ready' && state.phase !== 'saving') return null;
  const { prompt } = state;
  const saving = state.phase === 'saving';
  const error = state.phase === 'ready' ? state.error : '';

  async function record(action: DirectionCheckinAction) {
    try {
      await api.answerDirectionCheckin(leagueId, prompt.momentKey, action);
    } catch {
      // Only used to avoid asking again; the answer itself already took effect.
    }
  }

  async function answer(action: 'kept' | 'dismissed') {
    dispatch({ type: 'save' });
    await record(action);
    dispatch({ type: 'answered', action });
  }

  async function change(option: DirectionCheckinOption) {
    dispatch({ type: 'save' });
    setStance(option.value as TeamStance);
    await record('changed');
    dispatch({ type: 'answered', action: 'changed', label: option.label });
    onChanged?.();
  }

  return (
    <AccentCard accent={colors.accent}>
      <View style={styles.header}>
        <View style={styles.grow}>
          <AppText style={styles.title}>{prompt.headline}</AppText>
          <AppText style={styles.body}>{prompt.body}</AppText>
        </View>
        <PressableScale
          onPress={() => void answer('dismissed')}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Dismiss direction check-in"
          hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
        >
          <AppText style={styles.close}>✕</AppText>
        </PressableScale>
      </View>
      <View style={styles.actions}>
        <Button size="sm" label={prompt.keepLabel} loading={saving} disabled={saving} onPress={() => void answer('kept')} />
        {prompt.options.map((option) => (
          <Button key={option.value} size="sm" variant="secondary" label={directionSwitchLabel(option)} disabled={saving} onPress={() => void change(option)} />
        ))}
        <Button size="sm" variant="ghost" label={prompt.dismissLabel} disabled={saving} onPress={() => void answer('dismissed')} />
      </View>
      {error ? <AppText style={styles.error}>{error}</AppText> : null}
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    header: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    grow: { flex: 1, minWidth: 0, gap: spacing.xs },
    title: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    body: { fontSize: 14, lineHeight: 20, color: colors.textSecondary },
    close: { fontSize: 16, color: colors.textTertiary },
    actions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
    error: { fontSize: 13, color: colors.danger },
  });
}
