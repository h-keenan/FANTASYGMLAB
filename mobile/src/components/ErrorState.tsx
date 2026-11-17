import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import PremiumLock from './PremiumLock';
import { FREE_LEAGUE_CAP_MESSAGE } from '../lib/freeLeagueCap';
import Button from './Button';
import HelpLink from './HelpLink';
import IconCircle from './IconCircle';
import { useOptionalAuth } from '../context/AuthContext';
import { navigationRef } from '../navigation/navigationRef';
import {
  LEAGUE_GONE_ACTION,
  LEAGUE_GONE_BODY,
  LEAGUE_GONE_TITLE,
  SESSION_EXPIRED_ACTION,
  SESSION_EXPIRED_BODY,
  SESSION_EXPIRED_TITLE,
  classifyErrorMessage,
} from '../lib/badDayCopy';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/**
 * The one "couldn't load" state: danger icon, headline, the human-readable
 * reason, and a Retry button. Mirrors web-next's ErrorState. Screens used to
 * borrow `EmptyState` (no semantic error treatment) or print a bare red
 * line; `EmptyState` stays for true empty lists.
 */
export default function ErrorState({
  title = "Couldn't load this",
  message,
  onRetry,
  retryLabel = 'Try again',
  icon = 'alert-circle-outline',
  compact = false,
}: {
  title?: string;
  message?: string | null;
  onRetry?: () => void;
  retryLabel?: string;
  icon?: IconName;
  /** Inline variant for an error above content that is still on screen. */
  compact?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const auth = useOptionalAuth();
  const kind = message ? classifyErrorMessage(message) : 'other';
  if (message === FREE_LEAGUE_CAP_MESSAGE) {
    return <PremiumLock title="Your Free plan includes one league" description={message} feature="free_league_cap" />;
  }
  // Bad days with a better next step than "Try again": the session ended (clean re-login) or the league is gone (pick another).
  if ((kind === 'session' || kind === 'league_gone') && !compact) {
    const session = kind === 'session';
    const goBack = () => {
      if (session) void auth?.signOut();
      else if (navigationRef.isReady()) navigationRef.navigate('Home');
    };
    return (
      <View style={styles.container} accessibilityRole="alert" testID={session ? 'error-state-session' : 'error-state-league-gone'}>
        <IconCircle name="lock-closed-outline" color={colors.warning} size={56} iconSize={26} />
        <AppText style={styles.title}>{session ? SESSION_EXPIRED_TITLE : LEAGUE_GONE_TITLE}</AppText>
        <AppText style={styles.message}>{session ? SESSION_EXPIRED_BODY : LEAGUE_GONE_BODY}</AppText>
        <Button label={session ? SESSION_EXPIRED_ACTION : LEAGUE_GONE_ACTION} onPress={goBack} style={styles.button} />
      </View>
    );
  }
  return (
    <View style={[styles.container, compact && styles.compact]} accessibilityRole="alert">
      <IconCircle name={icon} color={colors.danger} size={compact ? 40 : 56} iconSize={compact ? 20 : 26} />
      <AppText style={styles.title}>{title}</AppText>
      {message ? <AppText style={styles.message}>{message}</AppText> : null}
      {onRetry ? <Button label={retryLabel} onPress={onRetry} style={styles.button} /> : null}
      <HelpLink context={{ topic: 'error_state', detail: message }} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: {
      alignItems: 'center',
      justifyContent: 'center',
      paddingVertical: spacing.xxl,
      paddingHorizontal: spacing.xl,
      gap: spacing.xs,
    },
    compact: { paddingVertical: spacing.lg },
    title: { fontSize: 16.5, fontWeight: '700', color: colors.textPrimary, textAlign: 'center', marginTop: spacing.sm },
    message: { fontSize: 14.5, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
    button: { marginTop: spacing.md, paddingVertical: spacing.sm },
  });
}
