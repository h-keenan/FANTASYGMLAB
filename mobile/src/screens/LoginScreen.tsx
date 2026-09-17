import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import * as AppleAuthentication from 'expo-apple-authentication';

import { useAuth } from '../context/AuthContext';
import { isAppleAuthAvailable, signInWithApple } from '../lib/appleAuth';
import { useGoogleSignIn } from '../lib/useGoogleSignIn';
import { colors, gradients, radii, spacing, typography } from '../theme';

export default function LoginScreen() {
  const { signIn, signUp, signInAsGuest } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'signIn' | 'signUp'>('signIn');
  const [submitting, setSubmitting] = useState(false);
  const [guestSubmitting, setGuestSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [appleAvailable, setAppleAvailable] = useState(false);
  const google = useGoogleSignIn();

  useEffect(() => {
    void isAppleAuthAvailable().then(setAppleAvailable);
  }, []);

  useEffect(() => {
    if (google.error) setError(google.error);
  }, [google.error]);

  const submit = async () => {
    setError(null);
    setNotice(null);
    setSubmitting(true);
    const result =
      mode === 'signIn' ? await signIn(email, password) : await signUp(email, password);
    setSubmitting(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    if (mode === 'signUp') {
      setNotice('Check your email to confirm your account, then sign in.');
    }
  };

  const onApplePress = async () => {
    setError(null);
    setNotice(null);
    const result = await signInWithApple();
    if (result.error) setError(result.error);
  };

  const onGuestPress = async () => {
    setError(null);
    setNotice(null);
    setGuestSubmitting(true);
    const result = await signInAsGuest();
    setGuestSubmitting(false);
    if (result.error) setError(result.error);
  };

  return (
    <View style={styles.root}>
      <LinearGradient colors={gradients.hero} style={styles.hero} />
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
        <Text style={styles.title}>FantasyGM Lab</Text>
        <Text style={styles.subtitle}>
          {mode === 'signIn' ? 'Sign in to your account' : 'Create an account'}
        </Text>

        {appleAvailable ? (
          <AppleAuthentication.AppleAuthenticationButton
            buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
            buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.WHITE}
            cornerRadius={radii.sm}
            style={styles.appleButton}
            onPress={onApplePress}
          />
        ) : null}

        {google.available ? (
          <TouchableOpacity
            style={[styles.socialButton, !google.ready && styles.buttonDisabled]}
            onPress={() => void google.signIn()}
            disabled={!google.ready || google.submitting}
          >
            {google.submitting ? (
              <ActivityIndicator color={colors.textPrimary} />
            ) : (
              <Text style={styles.socialButtonText}>Continue with Google</Text>
            )}
          </TouchableOpacity>
        ) : null}

        {appleAvailable || google.available ? (
          <View style={styles.dividerRow}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or</Text>
            <View style={styles.dividerLine} />
          </View>
        ) : null}

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={colors.textTertiary}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={colors.textTertiary}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}
        {notice ? <Text style={styles.notice}>{notice}</Text> : null}

        <TouchableOpacity
          style={[styles.button, (submitting || !email || !password) && styles.buttonDisabled]}
          onPress={submit}
          disabled={submitting || !email || !password}
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>
              {mode === 'signIn' ? 'Sign in' : 'Sign up'}
            </Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          onPress={() => setMode(mode === 'signIn' ? 'signUp' : 'signIn')}
        >
          <Text style={styles.switchMode}>
            {mode === 'signIn'
              ? "Don't have an account? Sign up"
              : 'Already have an account? Sign in'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity onPress={onGuestPress} disabled={guestSubmitting} style={styles.guestButton}>
          {guestSubmitting ? (
            <ActivityIndicator color={colors.textSecondary} />
          ) : (
            <>
              <Text style={styles.guestButtonText}>Continue as Guest</Text>
              <Text style={styles.guestCaption}>
                No account needed — a guest session can't be recovered if you lose this device.
              </Text>
            </>
          )}
        </TouchableOpacity>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  hero: { position: 'absolute', top: 0, left: 0, right: 0, height: '55%' },
  container: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
  },
  brandMark: {
    width: 72,
    height: 72,
    borderRadius: radii.md,
    alignSelf: 'center',
    marginBottom: spacing.md,
  },
  title: {
    ...typography.title,
    fontSize: 30,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  appleButton: {
    width: '100%',
    height: 48,
    marginBottom: spacing.sm,
  },
  socialButton: {
    height: 48,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSolid,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  socialButtonText: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  dividerRow: { flexDirection: 'row', alignItems: 'center', marginVertical: spacing.md },
  dividerLine: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.border },
  dividerText: { color: colors.textTertiary, fontSize: 12, marginHorizontal: spacing.sm },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 16,
    marginBottom: spacing.md,
    backgroundColor: colors.surfaceSolid,
    color: colors.textPrimary,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: radii.sm,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginTop: spacing.xs,
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  switchMode: {
    textAlign: 'center',
    marginTop: spacing.lg,
    color: colors.accent,
  },
  guestButton: {
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  guestButtonText: {
    color: colors.textSecondary,
    fontSize: 15,
    fontWeight: '600',
  },
  guestCaption: {
    color: colors.textTertiary,
    fontSize: 11,
    textAlign: 'center',
    marginTop: 4,
    paddingHorizontal: spacing.lg,
  },
  error: {
    color: colors.danger,
    marginBottom: spacing.sm,
  },
  notice: {
    color: colors.success,
    marginBottom: spacing.sm,
  },
});
