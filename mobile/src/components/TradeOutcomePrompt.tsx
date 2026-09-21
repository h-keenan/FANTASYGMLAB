import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, AppState, Modal, Pressable, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';

import { api, type PendingTradeOutcome, type TradeOutcomeAnswer } from '../lib/api';
import { colors, radii, spacing } from '../theme';

/**
 * "Did this trade happen?" — the follow-up half of Trade Outcomes.
 * Mounted once at the root (alongside GmOrb), not per-screen: pending
 * outcomes aren't scoped to whichever league/screen happens to be open, and
 * this should surface the same way regardless of where the app was left.
 * Checked on mount and whenever the app returns to the foreground — not
 * polled continuously, since a stale answer here is harmless (the next
 * foreground check catches it) and continuous polling would just be waste.
 */
export default function TradeOutcomePrompt() {
  const [queue, setQueue] = useState<PendingTradeOutcome[]>([]);
  const [answering, setAnswering] = useState(false);
  const checking = useRef(false);

  const checkPending = async () => {
    if (checking.current) return;
    checking.current = true;
    try {
      const result = await api.getPendingTradeOutcomes();
      setQueue(result.outcomes);
    } catch {
      // Silent — this is a courtesy prompt, not core functionality.
    } finally {
      checking.current = false;
    }
  };

  useEffect(() => {
    void checkPending();
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void checkPending();
    });
    return () => subscription.remove();
  }, []);

  const current = queue[0] ?? null;

  const answer = async (outcome: TradeOutcomeAnswer) => {
    if (!current || answering) return;
    setAnswering(true);
    try {
      await api.answerTradeOutcome(current.id, outcome);
      setQueue((prev) => prev.slice(1));
    } catch {
      // Leave it in the queue — they'll be asked again next foreground check.
    } finally {
      setAnswering(false);
    }
  };

  if (!current) return null;

  const summary = current.trade_summary;
  const sendNames = summary.send.map((a) => a.name).join(', ') || 'Nothing';
  const receiveNames = summary.receive.map((a) => a.name).join(', ') || 'Nothing';
  const partner = current.partner_team_name || summary.partner_team_name || 'your trade partner';

  return (
    <Modal visible transparent animationType="fade">
      <Pressable style={styles.backdrop}>
        <View style={styles.sheet}>
          <AppText style={styles.title}>Did this trade happen?</AppText>
          <AppText style={styles.subtitle}>You shared a trade with {partner}</AppText>
          <View style={styles.summaryCard}>
            <AppText style={styles.summaryLabel}>You sent</AppText>
            <AppText style={styles.summaryValue}>{sendNames}</AppText>
            <AppText style={styles.summaryLabel}>You received</AppText>
            <AppText style={styles.summaryValue}>{receiveNames}</AppText>
          </View>

          {answering ? (
            <ActivityIndicator color={colors.accent} style={styles.spinner} />
          ) : (
            <>
              <View style={styles.row}>
                <TouchableOpacity style={[styles.button, styles.yesButton]} onPress={() => void answer('yes')}>
                  <AppText style={styles.yesButtonText}>Yes, it happened</AppText>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.button, styles.noButton]} onPress={() => void answer('no')}>
                  <AppText style={styles.noButtonText}>No</AppText>
                </TouchableOpacity>
              </View>
              <View style={styles.row}>
                <TouchableOpacity
                  style={[styles.button, styles.secondaryButton]}
                  onPress={() => void answer('still_pending')}
                >
                  <AppText style={styles.secondaryButtonText}>Still pending</AppText>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.button, styles.secondaryButton]}
                  onPress={() => void answer('didnt_send')}
                >
                  <AppText style={styles.secondaryButtonText}>Didn't send</AppText>
                </TouchableOpacity>
              </View>
            </>
          )}
        </View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
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
    maxWidth: 400,
  },
  title: { fontSize: 17, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  subtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  summaryCard: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: spacing.md,
    marginBottom: spacing.md,
    gap: 2,
  },
  summaryLabel: { fontSize: 11, fontWeight: '700', color: colors.textTertiary, marginTop: spacing.xs },
  summaryValue: { fontSize: 14, color: colors.textPrimary },
  row: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  button: {
    flex: 1,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  yesButton: { backgroundColor: colors.success },
  yesButtonText: { color: '#fff', fontSize: 14, fontWeight: '700' },
  noButton: { backgroundColor: colors.danger },
  noButtonText: { color: '#fff', fontSize: 14, fontWeight: '700' },
  secondaryButton: { backgroundColor: colors.surfaceSolid, borderWidth: 1, borderColor: colors.border },
  secondaryButtonText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  spinner: { marginVertical: spacing.md },
});
