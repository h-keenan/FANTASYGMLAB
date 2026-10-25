import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import Input from './Input';
import ModalFormCard, { ModalFormActions, ModalFormHint, ModalFormTitle } from './ModalFormCard';
import { useAuth } from '../context/AuthContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { isAppleAuthAvailable, signInWithApple } from '../lib/appleAuth';
import type { GuestLinkFailure } from '../lib/guestConversion';
import { useGoogleSignIn } from '../lib/useGoogleSignIn';
import { spacing, type ThemeColors } from '../theme';

/**
 * Shared guest -> account upgrade form (email + password, in place on the
 * current anonymous session via AuthContext.convertGuestToAccount, so the
 * guest's id and saved data stay). Used by More ("Create account") and the
 * Paywall ("Create an account to start your free trial").
 */
export default function GuestCreateAccountModal({
  visible,
  onClose,
  hint = 'Your connected league carries over automatically — nothing to re-enter.',
}: {
  visible: boolean;
  onClose: () => void;
  hint?: string;
}) {
  const { convertGuestToAccount, signOut } = useAuth();
  const google = useGoogleSignIn({ linkGuest: true });
  const [appleAvailable, setAppleAvailable] = useState(false);
  const [failure, setFailure] = useState<GuestLinkFailure | null>(null);
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    void isAppleAuthAvailable().then(setAppleAvailable);
  }, []);

  // Google's link result arrives asynchronously through the hook.
  useEffect(() => {
    if (google.error) {
      setError(google.error);
      setFailure(google.failure);
    }
  }, [google.error, google.failure]);

  const close = () => {
    setFailure(null);
    setEmail('');
    setPassword('');
    setError(null);
    setNotice(null);
    onClose();
  };

  const submit = async () => {
    setError(null);
    setFailure(null);
    setNotice(null);
    setSubmitting(true);
    const result = await convertGuestToAccount(email, password);
    setSubmitting(false);
    if (result.error) {
      setError(result.error);
      setFailure(result.failure ?? null);
      return;
    }
    setNotice('Check your email to confirm your account. Your league stays connected once you do.');
  };

  const onApple = async () => {
    setError(null);
    setFailure(null);
    setSubmitting(true);
    // Links Apple to THIS guest user (same id) rather than signing in as a new user.
    const result = await signInWithApple({ linkGuest: true });
    setSubmitting(false);
    if (result.error) {
      setError(result.error);
      setFailure(result.failure ?? null);
      return;
    }
    close();
  };

  // Only offered after Supabase says the email/identity already belongs to an
  // account. Signing out drops the guest session, which the copy already warns about.
  const signInInstead = async () => {
    close();
    await signOut();
  };

  return (
    <ModalFormCard visible={visible} onClose={close}>
      <ModalFormTitle>Create account</ModalFormTitle>
      <ModalFormHint>{hint}</ModalFormHint>
      {appleAvailable ? (
        <Button label="Continue with Apple" variant="secondary" onPress={() => void onApple()} disabled={submitting} style={styles.input} />
      ) : null}
      {google.available ? (
        <Button
          label="Continue with Google"
          variant="secondary"
          onPress={() => void google.signIn()}
          disabled={!google.ready || google.submitting || submitting}
          loading={google.submitting}
          style={styles.input}
        />
      ) : null}
      <Input
        style={styles.input}
        placeholder="Email"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="email-address"
        textContentType="username"
        autoComplete="email"
        value={email}
        onChangeText={setEmail}
        editable={!submitting}
      />
      <Input
        style={styles.input}
        placeholder="Password"
        secureTextEntry
        textContentType="newPassword"
        autoComplete="new-password"
        value={password}
        onChangeText={setPassword}
        editable={!submitting}
      />
      {error ? <AppText style={styles.error}>{error}</AppText> : null}
      {failure === 'email-exists' || failure === 'identity-exists' ? (
        <Button label="Sign in instead" variant="ghost" onPress={() => void signInInstead()} />
      ) : null}
      {notice ? <AppText style={styles.notice}>{notice}</AppText> : null}
      <ModalFormActions
        onCancel={close}
        cancelDisabled={submitting}
        confirmLabel="Create account"
        onConfirm={submit}
        confirmDisabled={!email || !password}
        confirmLoading={submitting}
      />
    </ModalFormCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    input: { marginBottom: spacing.sm },
    error: { fontSize: 12, color: colors.danger, marginTop: spacing.xs, lineHeight: 16 },
    notice: { fontSize: 12, color: colors.success, marginTop: spacing.xs, lineHeight: 16 },
  });
}
