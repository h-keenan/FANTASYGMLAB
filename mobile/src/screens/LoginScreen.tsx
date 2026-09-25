import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import * as AppleAuthentication from 'expo-apple-authentication';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import AgeGate from '../components/AgeGate';
import BrandedSpinner from '../components/BrandedSpinner';
import ContentSections, { type ContentSection } from '../components/ContentSections';
import GridBackground from '../components/GridBackground';
import legalContent from '../data/legalContent.json';
import { useAuth } from '../context/AuthContext';
import { hasPassedAgeGate } from '../lib/ageGate';
import { isAppleAuthAvailable, signInWithApple } from '../lib/appleAuth';
import { useGoogleSignIn } from '../lib/useGoogleSignIn';
import { useThemeMode } from '../context/ThemeModeContext';
import { disabledOpacity, radii, spacing, typography, type ThemeColors } from '../theme';

const LEGAL_PAGES = (legalContent as { pages: Record<string, { title: string; sections: ContentSection[] }> }).pages;

export default function LoginScreen() {
  const { signIn, signUp, signInAsGuest } = useAuth();
  const { colors } = useThemeMode();
  const insets = useSafeAreaInsets();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'signIn' | 'signUp'>('signIn');
  const [submitting, setSubmitting] = useState(false);
  const [guestSubmitting, setGuestSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [appleAvailable, setAppleAvailable] = useState(false);
  const [ageVerified, setAgeVerified] = useState<boolean | null>(null);
  const [legalPageKey, setLegalPageKey] = useState<string | null>(null);
  const google = useGoogleSignIn();

  useEffect(() => {
    void isAppleAuthAvailable().then(setAppleAvailable);
  }, []);

  useEffect(() => {
    void hasPassedAgeGate().then(setAgeVerified);
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

  if (ageVerified === null) {
    return (
      <View style={styles.root}>
        <GridBackground />
        <View style={styles.initialLoading}>
          <BrandedSpinner />
        </View>
      </View>
    );
  }
  if (!ageVerified) {
    return <AgeGate onPassed={() => setAgeVerified(true)} />;
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Image source={require('../../assets/icon.png')} style={styles.brandMark} />
        <AppText style={styles.title}>FantasyGM Lab</AppText>
        <AppText style={styles.subtitle}>
          {mode === 'signIn' ? 'Sign in to your account' : 'Create an account'}
        </AppText>

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
              <AppText style={styles.socialButtonText}>Continue with Google</AppText>
            )}
          </TouchableOpacity>
        ) : null}

        {appleAvailable || google.available ? (
          <View style={styles.dividerRow}>
            <View style={styles.dividerLine} />
            <AppText style={styles.dividerText}>or</AppText>
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

        {error ? <AppText style={styles.error}>{error}</AppText> : null}
        {notice ? <AppText style={styles.notice}>{notice}</AppText> : null}

        <TouchableOpacity
          style={[styles.button, (submitting || !email || !password) && styles.buttonDisabled]}
          onPress={submit}
          disabled={submitting || !email || !password}
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <AppText style={styles.buttonText}>
              {mode === 'signIn' ? 'Sign in' : 'Sign up'}
            </AppText>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          onPress={() => setMode(mode === 'signIn' ? 'signUp' : 'signIn')}
        >
          <AppText style={styles.switchMode}>
            {mode === 'signIn'
              ? "Don't have an account? Sign up"
              : 'Already have an account? Sign in'}
          </AppText>
        </TouchableOpacity>

        <TouchableOpacity onPress={onGuestPress} disabled={guestSubmitting} style={styles.guestButton}>
          {guestSubmitting ? (
            <ActivityIndicator color={colors.textSecondary} />
          ) : (
            <>
              <AppText style={styles.guestButtonText}>Continue as Guest</AppText>
              <AppText style={styles.guestCaption}>
                No account needed — a guest session can't be recovered if you lose this device.
              </AppText>
            </>
          )}
        </TouchableOpacity>

        <View style={styles.legalRow}>
          <AppText style={styles.legalLink} onPress={() => setLegalPageKey('terms')}>
            Terms of Use
          </AppText>
          <AppText style={styles.legalDivider}>·</AppText>
          <AppText style={styles.legalLink} onPress={() => setLegalPageKey('privacy')}>
            Privacy Policy
          </AppText>
        </View>
      </KeyboardAvoidingView>

      <Modal visible={legalPageKey !== null} animationType="slide" onRequestClose={() => setLegalPageKey(null)}>
        <View style={styles.root}>
          <GridBackground />
          <View style={[styles.legalModalHeader, { paddingTop: insets.top + spacing.md }]}>
            <AppText style={styles.legalModalTitle}>{legalPageKey ? LEGAL_PAGES[legalPageKey]?.title : ''}</AppText>
            <Pressable onPress={() => setLegalPageKey(null)} hitSlop={12}>
              <AppText style={styles.legalModalClose}>Done</AppText>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.legalModalContent}>
            {legalPageKey ? <ContentSections sections={LEGAL_PAGES[legalPageKey]?.sections ?? []} /> : null}
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  initialLoading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
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
  buttonDisabled: { opacity: disabledOpacity },
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
    fontWeight: '500',
  },
  guestCaption: {
    color: colors.textTertiary,
    fontSize: 11,
    textAlign: 'center',
    marginTop: 4,
    paddingHorizontal: spacing.lg,
  },
  legalRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: spacing.xl,
  },
  legalLink: {
    color: colors.textTertiary,
    fontSize: 12,
    textDecorationLine: 'underline',
  },
  legalDivider: {
    color: colors.textTertiary,
    fontSize: 12,
    marginHorizontal: spacing.sm,
  },
  legalModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.md,
  },
  legalModalTitle: { ...typography.title, fontSize: 20, color: colors.textPrimary, flexShrink: 1 },
  legalModalClose: { color: colors.accent, fontSize: 16, fontWeight: '600' },
  legalModalContent: { paddingHorizontal: spacing.xl, paddingBottom: spacing.xl * 2 },
  error: {
    color: colors.danger,
    marginBottom: spacing.sm,
  },
  notice: {
    color: colors.success,
    marginBottom: spacing.sm,
  },
  });
}
