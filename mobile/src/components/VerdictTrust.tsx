import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  VERDICT_FEEDBACK_REASONS,
  VERDICT_TRUST_COPY,
  type VerdictAssumptions,
  type VerdictFeedbackReason,
} from '../lib/verdictTrust';
import { LINK_HIT_SLOP, radii, spacing, type ThemeColors } from '../theme';

type Status = 'idle' | 'choosing' | 'sending' | 'sent' | 'failed';

export interface VerdictReportContext {
  surface: 'trade_analyzer' | 'trade_hub' | 'trade_finder';
  platform: 'ios' | 'android';
  leagueId: string;
  lens: string;
  strategy: string;
  sendIds: string[];
  receiveIds: string[];
  verdictLabel: string;
  confidence: string;
  valueDelta: number | null;
  assumptionsLine: string;
}

/**
 * Under a trade verdict: what it assumed (tap to expand) and "Report a bad
 * verdict": one fixed reason, no free text, stored anonymously server-side.
 * Mirrors web VerdictTrust.
 */
export default function VerdictTrust({
  assumptions,
  context,
}: {
  assumptions: VerdictAssumptions | null | undefined;
  context: VerdictReportContext;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [status, setStatus] = useState<Status>('idle');
  const [expanded, setExpanded] = useState(false);

  const send = async (reason: VerdictFeedbackReason) => {
    setStatus('sending');
    try {
      const result = await api.postVerdictFeedback(reason, context);
      setStatus(result.ok ? 'sent' : 'failed');
    } catch {
      setStatus('failed');
    }
  };

  return (
    <View style={styles.wrap} testID="verdict-trust">
      {assumptions ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={VERDICT_TRUST_COPY.assumptionsTitle}
          accessibilityState={{ expanded }}
          onPress={() => setExpanded((value) => !value)}
          hitSlop={LINK_HIT_SLOP}
        >
          <AppText style={styles.muted} numberOfLines={expanded ? undefined : 2}>
            {assumptions.line}
          </AppText>
          {expanded
            ? assumptions.items.map((item) => (
                <AppText key={item.key} style={styles.item}>
                  {item.label}: {item.value}
                </AppText>
              ))
            : null}
        </Pressable>
      ) : null}

      {status === 'sent' ? (
        <AppText style={styles.thanks}>{VERDICT_TRUST_COPY.thanks}</AppText>
      ) : status === 'idle' ? (
        <Pressable accessibilityRole="button" hitSlop={LINK_HIT_SLOP} onPress={() => setStatus('choosing')}>
          <AppText style={styles.reportLink}>{VERDICT_TRUST_COPY.report}</AppText>
        </Pressable>
      ) : (
        <View style={styles.reasons}>
          <AppText style={styles.prompt}>{VERDICT_TRUST_COPY.reportPrompt}</AppText>
          {VERDICT_FEEDBACK_REASONS.map((reason) => (
            <Button
              key={reason.key}
              size="sm"
              variant="secondary"
              label={reason.label}
              disabled={status === 'sending'}
              onPress={() => void send(reason.key)}
            />
          ))}
          {status === 'sending' ? <AppText style={styles.muted}>{VERDICT_TRUST_COPY.sending}</AppText> : null}
          {status === 'failed' ? <AppText style={styles.error}>{VERDICT_TRUST_COPY.failed}</AppText> : null}
          <Pressable accessibilityRole="button" hitSlop={LINK_HIT_SLOP} onPress={() => setStatus('idle')}>
            <AppText style={styles.muted}>{VERDICT_TRUST_COPY.cancel}</AppText>
          </Pressable>
        </View>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm, marginTop: spacing.sm },
    muted: { fontSize: 12, color: colors.textTertiary },
    item: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
    reportLink: { fontSize: 12, fontWeight: '700', color: colors.textTertiary, textDecorationLine: 'underline' },
    prompt: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    reasons: { gap: spacing.xs, padding: spacing.md, borderRadius: radii.md, borderWidth: 1, borderColor: colors.border },
    thanks: { fontSize: 14, color: colors.success },
    error: { fontSize: 12, color: colors.danger },
  });
}
