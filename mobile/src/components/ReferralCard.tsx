import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Share, StyleSheet, View } from 'react-native';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import Button from './Button';
import ErrorState from './ErrorState';
import SectionHeading from './SectionHeading';
import SkeletonBlock from './SkeletonBlock';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type ReferralStatusResponse } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { referralRewardCopy } from '../lib/liveDraft';
import { spacing, type ThemeColors } from '../theme';

/**
 * Account "Invite friends" card (port of web-next's ReferralCard), backed by
 * GET /v1/referrals/my-code. Differs from web only in the action: the native
 * share sheet (which offers Copy) replaces the readonly input + clipboard
 * button, since no clipboard module ships in the app.
 */
export default function ReferralCard() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [referral, setReferral] = useState<ReferralStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getMyReferralCode()
      .then((result) => {
        if (cancelled) return;
        setReferral(result);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(toUserErrorMessage(err, 'Could not load your invite link.'));
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const onShare = useCallback(async () => {
    if (!referral?.link) return;
    try {
      await Share.share({ message: `Join me on FantasyDesk: ${referral.link}`, url: referral.link });
    } catch {
      // User dismissed or sharing unavailable; nothing to recover.
    }
  }, [referral]);

  return (
    <View>
      <SectionHeading title="Invite friends" icon="gift-outline" />
      <AnimatedCard style={styles.card}>
        {error ? (
          <ErrorState
            compact
            title="Couldn't load your invite link"
            message={error}
            onRetry={() => {
              setError(null);
              setTick((n) => n + 1);
            }}
          />
        ) : !referral ? (
          <SkeletonBlock height={72} />
        ) : (
          <>
            <AppText style={styles.body}>{referralRewardCopy(referral)}</AppText>
            <View style={styles.linkBox}>
              <AppText style={styles.link} numberOfLines={1} selectable>
                {referral.link}
              </AppText>
            </View>
            <Button label="Share invite link" onPress={onShare} />
            <View style={styles.statRow}>
              <AppText style={styles.label}>Friends joined</AppText>
              <AppText style={styles.value}>
                {referral.connected_count === 0 ? 'None yet, share your link' : referral.connected_count}
              </AppText>
            </View>
            <View style={styles.statRow}>
              <AppText style={styles.label}>Free months earned</AppText>
              <AppText style={styles.value}>
                {referral.comp_months_granted} / {referral.max_comp_months}
              </AppText>
            </View>
            {referral.comp_is_active ? (
              <View style={styles.statRow}>
                <AppText style={styles.label}>Reward status</AppText>
                <ToneBadge
                  label={`Active${referral.comp_until ? ` through ${new Date(referral.comp_until).toLocaleDateString()}` : ''}`}
                  color={colors.success}
                />
              </View>
            ) : null}
          </>
        )}
      </AnimatedCard>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { padding: spacing.md, gap: spacing.md },
    body: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
    linkBox: { borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
    link: { fontSize: 13, color: colors.textPrimary },
    statRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    label: { fontSize: 13, color: colors.textSecondary },
    value: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, flexShrink: 1, textAlign: 'right' },
  });
}
