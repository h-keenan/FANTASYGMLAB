import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, AppState, Pressable, TouchableOpacity, View, StyleSheet } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import {
  ApiError,
  api,
  type GuessThePlayerNameMatchCorrectPairing,
  type GuessThePlayerNameMatchResponse,
} from '../lib/api';
import {
  getDismissedGuessThePlayerNameMatchPickId,
  setDismissedGuessThePlayerNameMatchPickId,
} from '../lib/guessThePlayerNameMatchDismissed';
import {
  guessThePlayerStreakCaption,
  shouldShowGuessThePlayerNameMatchPrompt,
} from '../lib/guessThePlayerNameMatchPrompt';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, typography, type ThemeColors, scrim } from '../theme';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';

type RevealState = {
  correct: boolean;
  correctPairing: GuessThePlayerNameMatchCorrectPairing;
};

/**
 * "Who is who?" daily mini-game — a SECOND, distinct popup alongside
 * GuessThePlayerPrompt.tsx (coridian_, 2026-10-19, same Discord thread):
 * "you get two players and one player is, you know, a known name that's
 * good, and then one player is kind of an unknown name who maybe has
 * better stats than the known name, and so you pick and choose who is
 * who." Unlike that game, BOTH players' real identity is shown up front —
 * what's hidden is which of the two real, unlabeled stat lines belongs to
 * which player. Mounted once at the root (RootNavigator.tsx, alongside
 * GmOrb/TradeOutcomePrompt/GuessThePlayerPrompt) for the same reason that
 * one is: one global floating thing, decides for itself whether to show,
 * checked on mount + every foreground resume.
 *
 * "Shown once per day" uses the same two-source-of-truth shape as
 * GuessThePlayerPrompt.tsx: already ANSWERED today -> GET's own
 * `already_answered` flag; closed WITHOUT answering -> lib/
 * guessThePlayerNameMatchDismissed.ts's own AsyncStorage key (distinct
 * from that game's key, so dismissing one never suppresses the other).
 */
export default function GuessThePlayerNameMatchPrompt() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  const [response, setResponse] = useState<GuessThePlayerNameMatchResponse | null>(null);
  const [dismissedPickId, setDismissedPickId] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reveal, setReveal] = useState<RevealState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadedDismissed = useRef(false);

  const applyResponse = (result: GuessThePlayerNameMatchResponse) => {
    setResponse(result);
    if (result.already_answered && result.correct_pairing) {
      setReveal({ correct: result.last_result === 'correct', correctPairing: result.correct_pairing });
      setSelectedSlot(result.correct_pairing.famous_slot);
    }
  };

  const fetchPrompt = async () => {
    try {
      const result = await api.getGuessThePlayerNameMatch();
      applyResponse(result);
    } catch {
      // Silent on failure — this is a bonus daily extra, never something
      // that should block or interrupt the rest of the app.
      setResponse(null);
    }
  };

  useEffect(() => {
    (async () => {
      setDismissedPickId(await getDismissedGuessThePlayerNameMatchPickId());
      loadedDismissed.current = true;
      await fetchPrompt();
    })();
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active' && loadedDismissed.current) void fetchPrompt();
    });
    return () => subscription.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = shouldShowGuessThePlayerNameMatchPrompt(response, dismissedPickId);
  if (!visible || !response?.prompt) return null;
  const prompt = response.prompt;
  const slotEntries = Object.entries(prompt.slots).sort(([a], [b]) => a.localeCompare(b));

  function dismiss() {
    setDismissedPickId(prompt.pick_id);
    void setDismissedGuessThePlayerNameMatchPickId(prompt.pick_id);
  }

  async function handleGuess(slot: string) {
    if (reveal || submitting) return;
    setSelectedSlot(slot);
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.answerGuessThePlayerNameMatch(prompt.pick_id, slot);
      setReveal({ correct: result.correct, correctPairing: result.correct_pairing });
      setResponse((previous) => (previous ? { ...previous, streak: result.streak, already_answered: true } : previous));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        // Today's pairing rotated out from under this popup (day rolled
        // over mid-guess) — refetch rather than score against stale data.
        setError('This round just ended. Refreshing.');
        try {
          const refreshed = await api.getGuessThePlayerNameMatch();
          setSelectedSlot(null);
          setError(null);
          applyResponse(refreshed);
        } catch {
          setError('Could not refresh. Try again later.');
        }
      } else {
        setSelectedSlot(null);
        setError('Could not submit your guess. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SheetModal visible transparent animationType="fade" onRequestClose={dismiss}>
      <Pressable style={styles.backdrop}>
        <SwipeDismissCard style={styles.sheet} onDismiss={dismiss} testID="guess-the-player-name-match-prompt">
          <View style={styles.headerRow}>
            <View style={styles.headerText}>
              <AppText style={styles.kicker}>Name Match</AppText>
              <AppText style={styles.title}>Who Is Who?</AppText>
            </View>
            <TouchableOpacity onPress={dismiss} hitSlop={8} accessibilityLabel="Dismiss Name Match">
              <AppText style={styles.closeGlyph}>{'✕'}</AppText>
            </TouchableOpacity>
          </View>

          <View style={styles.identitiesRow}>
            {[
              { identity: prompt.famous_player, kicker: 'Known Name' },
              { identity: prompt.obscure_player, kicker: 'Unknown Name' },
            ].map(({ identity, kicker }) => (
              <View key={identity.player_id} style={styles.identityColumn}>
                <PlayerAvatar playerId={identity.player_id} tier={identity.tier} size={48} />
                <AppText style={styles.identityKicker}>{kicker}</AppText>
                <AppText style={styles.name}>{identity.name}</AppText>
                <View style={styles.identityMetaRow}>
                  <PositionBadge position={identity.position} />
                  <AppText style={styles.metaText}>{identity.team}</AppText>
                </View>
              </View>
            ))}
          </View>

          <AppText style={styles.promptText}>
            Which stat line belongs to {prompt.famous_player.name}? Week {prompt.week} {'·'} {prompt.season}
          </AppText>

          <View style={styles.slotsColumn}>
            {slotEntries.map(([slot, payload]) => {
              const isSelected = selectedSlot === slot;
              const isCorrectSlot = Boolean(reveal) && slot === reveal?.correctPairing.famous_slot;
              const isWrongSelection = Boolean(reveal) && isSelected && !isCorrectSlot;
              let backgroundColor: string = colors.surface;
              let borderColor: string = colors.border;
              if (isCorrectSlot) {
                backgroundColor = `${colors.success}26`;
                borderColor = colors.success;
              } else if (isWrongSelection) {
                borderColor = colors.danger;
              } else if (isSelected) {
                borderColor = colors.accent;
              }
              const faded = Boolean(reveal) && !isCorrectSlot && !isWrongSelection;
              return (
                <TouchableOpacity
                  key={slot}
                  disabled={Boolean(reveal) || submitting}
                  onPress={() => void handleGuess(slot)}
                  style={[styles.slotButton, { backgroundColor, borderColor, opacity: faded ? 0.6 : 1 }]}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: isSelected }}
                  accessibilityLabel={`Stat Line ${slot}`}
                >
                  <AppText style={styles.slotKicker}>{'Stat Line '}{slot}</AppText>
                  <View style={styles.statLineRow}>
                    {payload.stat_line.map((item) => (
                      <AppText key={item.label} style={styles.statItem}>
                        <AppText style={styles.statValue}>{item.value}</AppText>{' '}
                        <AppText style={styles.metaText}>{item.label}</AppText>
                      </AppText>
                    ))}
                    <AppText style={styles.statItem}>
                      <AppText style={styles.statValue}>{payload.fantasy_points_ppr}</AppText>{' '}
                      <AppText style={styles.metaText}>Fantasy Points (PPR)</AppText>
                    </AppText>
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>

          {submitting ? <ActivityIndicator color={colors.accent} style={styles.spinner} /> : null}

          {reveal ? (
            <AppText style={[styles.resultText, { color: reveal.correct ? colors.success : colors.danger }]}>
              {reveal.correct ? 'Correct!' : 'Not quite.'} The lesser-known name actually had the better week!
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
      backgroundColor: scrim,
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
    identitiesRow: { flexDirection: 'row', gap: spacing.md },
    identityColumn: { flex: 1, gap: 2 },
    identityKicker: { ...typography.caption, color: colors.textTertiary, textTransform: 'uppercase' },
    name: { ...typography.body, fontWeight: '700', color: colors.textPrimary },
    identityMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
    metaText: { ...typography.caption, color: colors.textSecondary },
    promptText: { ...typography.body, color: colors.textSecondary },
    slotsColumn: { gap: spacing.sm },
    slotButton: {
      borderWidth: 1,
      borderRadius: radii.md,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      gap: 4,
    },
    slotKicker: { ...typography.caption, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase' },
    statLineRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
    statItem: { ...typography.body, color: colors.textPrimary },
    statValue: { fontWeight: '700', color: colors.textPrimary },
    spinner: { marginVertical: spacing.xs },
    resultText: { ...typography.body, fontWeight: '700' },
    errorText: { ...typography.caption, color: colors.danger },
    streakText: { ...typography.caption, color: colors.textTertiary },
  });
}
