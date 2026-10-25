import React, { useMemo, useState } from 'react';
import { StyleSheet } from 'react-native';

import AppText from './AppText';
import Input from './Input';
import ModalFormCard, { ModalFormActions, ModalFormHint, ModalFormTitle } from './ModalFormCard';
import { useAuth } from '../context/AuthContext';
import { useThemeMode } from '../context/ThemeModeContext';
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
  const { convertGuestToAccount } = useAuth();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const close = () => {
    setEmail('');
    setPassword('');
    setError(null);
    setNotice(null);
    onClose();
  };

  const submit = async () => {
    setError(null);
    setNotice(null);
    setSubmitting(true);
    const result = await convertGuestToAccount(email, password);
    setSubmitting(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setNotice('Check your email to confirm your account. Your league stays connected once you do.');
  };

  return (
    <ModalFormCard visible={visible} onClose={close}>
      <ModalFormTitle>Create account</ModalFormTitle>
      <ModalFormHint>{hint}</ModalFormHint>
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
