import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, AppState, Pressable, TouchableOpacity, View, StyleSheet } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import {
  ApiError,
  api,
  type GuessThePlayerCorrectIdentity,
  type GuessThePlayerOption,
  type GuessThePlayerResponse,
} from '../lib/api';
import {
  getDismissedGuessThePlayerPickId,
  setDismissedGuessThePlayerPickId,
} from '../lib/guessThePlayerDismissed';
import { guessThePlayerStreakCaption, shouldShowGuessThePlayerPrompt } from '../lib/guessThePlayerPrompt';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, typography, type ThemeColors } from '../theme';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';

type RevealState = {
  correct: boolean;
  correctPlayer: GuessThePlayerCorrectIdentity;
};

/**
 * "Whose stats are these?" daily mini-game — coridian_, 2026-10-19 (same
 * Discord spec that shipped the web Dashboard card, web-next/src/components/
 * GuessThePlayerCard.tsx): "on the app it would be a pop-up." Mounted once
 * at the root (RootNavigator.tsx, alongside GmOrb/TradeOutcomePrompt) rather
 * than embedded in HomeScreen itself — same "one global floating thing,
 * decides for itself whether to show" shape TradeOutcomePrompt already
 * uses, so it surfaces the same way regardless of which screen the app
 * happens to resume on, and checked on mount + every foreground resume (so
 * a day rollover while backgrounded still shows today's new pick without
 * needing to kill/reopen the app).
 *
 * "Shown once per day" has two different sources of truth, deliberately:
 *   - Already ANSWERED today -> GET's own `already_answered` flag already
 *     covers this, no local state needed.
 *   - Closed WITHOUT answering -> the backend has no way to know that, so
 *     lib/guessThePlayerDismissed.ts keeps one AsyncStorage key (today's
 *     `pick_id`, not a plain boolean, so a new day's new pick_id is never
 *     suppressed by a stale dismiss) — the same single-key shape
 *     lib/trialLapsedSeen.ts already uses for its own "shown once" gate.
 * See lib/guessThePlayerPrompt.ts's shouldShowGuessThePlayerPrompt for the
 * actual combined decision (and its test file for the cases it covers).
 */
export default function GuessThePlayerPrompt() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  const [response, setResponse] = useState<GuessThePlayerResponse | null>(null);
  const [dismissedPickId, setDismissedPickId] = useState<string | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reveal, setReveal] = useState<RevealState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadedDismissed = useRef(false);

  const applyResponse = (result: GuessThePlayerResponse) => {
    setResponse(result);
    if (result.already_answered && result.correct_player) {
      setReveal({ correct: result.last_result === 'correct', correctPlayer: result.correct_player });
      setSelectedPlayerId(result.correct_player.player_id);
    }
  };

  const fetchPrompt = async () => {
    try {
      const result = await api.getGuessThePlayer();
      applyResponse(result);
    } catch {
      // Silent on failure — this is a bonus daily extra, never something
      // that should block or interrupt the rest of the app.
      setResponse(null);
    }
  };

  useEffect(() => {
    (async () => {
      setDismissedPickId(await getDismissedGuessThePlayerPickId());
      loadedDismissed.current = true;
      await fetchPrompt();
    })();
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active' && loadedDismissed.current) void fetchPrompt();
    });
    return () => subscription.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // `dismissedPickId` always finishes loading from storage before `response`
  // is ever set (both awaited in sequence in the mount effect above), so
  // gating on `response` having real data is already enough to guarantee
  // the dismissed-check below never runs against a not-yet-loaded `null`.
  const visible = shouldShowGuessThePlayerPrompt(response, dismissedPickId);
  if (!visible || !response?.prompt) return null;
  const prompt = response.prompt;

  function dismiss() {
    setDismissedPickId(prompt.pick_id);
    void setDismissedGuessThePlayerPickId(prompt.pick_id);
  }

  async function handleGuess(option: GuessThePlayerOption) {
    if (reveal || submitting) return;
    setSelectedPlayerId(option.player_id);
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.answerGuessThePlayer(prompt.pick_id, option.player_id);
      setReveal({ correct: result.correct, correctPlayer: result.correct_player });
      setResponse((previous) => (previous ? { ...previous, streak: result.streak, already_answered: true } : previous));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        // Today's pick rotated out from under this popup (day rolled over
        // mid-guess) — refetch rather than score against stale data.
        setError('This round just ended. Refreshing.');
        try {
          const refreshed = await api.getGuessThePlayer();
          setSelectedPlayerId(null);
          setError(null);
          applyResponse(refreshed);
        } catch {
          setError('Could not refresh. Try again later.');
        }
      } else {
        setSelectedPlayerId(null);
        setError('Could not submit your guess. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SheetModal visible transparent animationType="fade" onRequestClose={dismiss}>
      <Pressable style={styles.backdrop}>
        <SwipeDismissCard style={styles.sheet} onDismiss={dismiss} testID="guess-the-player-prompt">
          <View style={styles.headerRow}>
            <View style={styles.headerText}>
              <AppText style={styles.kicker}>Guess the Player</AppText>
              <AppText style={styles.title}>Whose stats are these?</AppText>
            </View>
            <TouchableOpacity onPress={dismiss} hitSlop={8} accessibilityLabel="Dismiss Guess the Player">
              <AppText style={styles.closeGlyph}>{'✕'}</AppText>
            </TouchableOpacity>
          </View>

          <View style={styles.identityRow}>
            <PlayerAvatar playerId={reveal ? reveal.correctPlayer.player_id : null} tier={prompt.tier} size={56} />
            <View style={styles.identityText}>
              {reveal ? (
                <AppText style={styles.name}>{reveal.correctPlayer.name}</AppText>
              ) : (
                <AppText style={[styles.name, { color: colors.textTertiary }]}>??? ???</AppText>
              )}
              <View style={styles.identityMetaRow}>
                <PositionBadge position={reveal ? reveal.correctPlayer.position : prompt.position} />
                {reveal ? <AppText style={styles.metaText}>{reveal.correctPlayer.team}</AppText> : null}
                <AppText style={styles.metaText}>
                  Week {prompt.week} {'·'} {prompt.season}
                </AppText>
              </View>
            </View>
          </View>

          <View style={styles.statLineRow}>
            {prompt.stat_line.map((item) => (
              <AppText key={item.label} style={styles.statItem}>
                <AppText style={styles.statValue}>{item.value}</AppText>{' '}
                <AppText style={styles.metaText}>{item.label}</AppText>
              </AppText>
            ))}
            <AppText style={styles.statItem}>
              <AppText style={styles.statValue}>{prompt.fantasy_points_ppr}</AppText>{' '}
              <AppText style={styles.metaText}>Fantasy Points (PPR)</AppText>
            </AppText>
          </View>

          <View style={styles.optionsColumn}>
            {prompt.options.map((option) => {
              const isSelected = selectedPlayerId === option.player_id;
              const isCorrectOption = Boolean(reveal) && option.player_id === reveal?.correctPlayer.player_id;
              const isWrongSelection = Boolean(reveal) && isSelected && !isCorrectOption;
              let backgroundColor: string = colors.surface;
              let borderColor: string = colors.border;
              if (isCorrectOption) {
                backgroundColor = `${colors.success}26`;
                borderColor = colors.success;
              } else if (isWrongSelection) {
                borderColor = colors.danger;
              } else if (isSelected) {
                borderColor = colors.accent;
              }
              const faded = Boolean(reveal) && !isCorrectOption && !isWrongSelection;
              return (
                <TouchableOpacity
                  key={option.player_id}
                  disabled={Boolean(reveal) || submitting}
                  onPress={() => void handleGuess(option)}
                  style={[styles.optionButton, { backgroundColor, borderColor, opacity: faded ? 0.6 : 1 }]}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: isSelected }}
                >
                  <AppText style={styles.optionText}>{option.name}</AppText>
                </TouchableOpacity>
              );
            })}
          </View>

          {submitting ? <ActivityIndicator color={colors.accent} style={styles.spinner} /> : null}

          {reveal ? (
            <AppText style={[styles.resultText, { color: reveal.correct ? colors.success : colors.danger }]}>
              {reveal.correct ? 'Correct!' : `Not quite. It was ${reveal.correctPlayer.name}.`}
            </AppText>
          ) : null}

          {error ? <AppText style={styles.errorText}>{error}</AppText> : null}

          <AppText style={styles.streakText}>{guessThePlayerStreakCaption(response.streak)}</AppText>
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: 'rgba(0,0,0,0.6)',
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.lg,
    },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
      width: '100%',
      maxWidth: 420,
      gap: spacing.md,
    },
    headerRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.sm },
    headerText: { flex: 1, gap: 2 },
    kicker: { ...typography.kicker, color: colors.accent, textTransform: 'uppercase' },
    title: { ...typography.heading, color: colors.textPrimary },
    closeGlyph: { fontSize: 15, color: colors.textTertiary, paddingTop: 2 },
    identityRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    identityText: { flex: 1, gap: 4 },
    name: { ...typography.heading, color: colors.textPrimary },
    identityMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
    metaText: { ...typography.caption, color: colors.textSecondary },
    statLineRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
    statItem: { ...typography.body, color: colors.textPrimary },
    statValue: { fontWeight: '700', color: colors.textPrimary },
    optionsColumn: { gap: spacing.sm },
    optionButton: {
      borderWidth: 1,
      borderRadius: radii.md,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
    },
    optionText: { ...typography.body, fontWeight: '700', color: colors.textPrimary },
    spinner: { marginVertical: spacing.xs },
    resultText: { ...typography.body, fontWeight: '700' },
    errorText: { ...typography.caption, color: colors.danger },
    streakText: { ...typography.caption, color: colors.textTertiary },
  });
}
