import React, { useMemo, useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';

import { calculateAge, MINIMUM_AGE, setPassedAgeGate } from '../lib/ageGate';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, typography, type ThemeColors } from '../theme';

/**
 * Neutral date-of-birth gate shown once per device before LoginScreen's
 * actual sign-in/sign-up UI — deliberately a DOB entry, not an "I am 13 or
 * older" checkbox, which the FTC treats as coaching the answer rather than
 * a real age check. Blocks every auth path uniformly (email, Apple,
 * Google, guest all live behind the same LoginScreen), since none of them
 * otherwise collect an age at all.
 *
 * Nothing here is persisted for an under-13 result — no AsyncStorage write,
 * no account, no network call. A pass just sets a plain local boolean flag
 * (see lib/ageGate.ts) so a returning adult isn't asked again.
 */
export default function AgeGate({ onPassed }: { onPassed: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [month, setMonth] = useState('');
  const [day, setDay] = useState('');
  const [year, setYear] = useState('');
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    const m = Number(month);
    const d = Number(day);
    const y = Number(year);
    if (!m || !d || !y || m < 1 || m > 12 || d < 1 || d > 31 || y < 1900 || y > new Date().getFullYear()) {
      setError('Enter a valid date of birth.');
      return;
    }
    const birthDate = new Date(y, m - 1, d);
    if (birthDate.getMonth() !== m - 1 || birthDate.getDate() !== d) {
      setError('Enter a valid date of birth.');
      return;
    }
    const age = calculateAge(birthDate);
    if (age < MINIMUM_AGE) {
      setBlocked(true);
      return;
    }
    void setPassedAgeGate();
    onPassed();
  };

  if (blocked) {
    return (
      <View style={styles.root}>
        <View style={styles.card}>
          <AppText style={styles.title}>Age Requirement</AppText>
          <AppText style={styles.body}>
            You must be at least {MINIMUM_AGE} years old to use FantasyGM Lab. Nothing you entered has been saved.
          </AppText>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.card}>
          <AppText style={styles.title}>Before you continue</AppText>
          <AppText style={styles.body}>Please enter your date of birth.</AppText>
          <View style={styles.row}>
            <TextInput
              style={[styles.input, styles.inputSmall]}
              placeholder="MM"
              placeholderTextColor={colors.textTertiary}
              keyboardType="number-pad"
              maxLength={2}
              value={month}
              onChangeText={setMonth}
            />
            <TextInput
              style={[styles.input, styles.inputSmall]}
              placeholder="DD"
              placeholderTextColor={colors.textTertiary}
              keyboardType="number-pad"
              maxLength={2}
              value={day}
              onChangeText={setDay}
            />
            <TextInput
              style={[styles.input, styles.inputLarge]}
              placeholder="YYYY"
              placeholderTextColor={colors.textTertiary}
              keyboardType="number-pad"
              maxLength={4}
              value={year}
              onChangeText={setYear}
            />
          </View>
          {error ? <AppText style={styles.error}>{error}</AppText> : null}
          <TouchableOpacity
            style={[styles.button, (!month || !day || !year) && styles.buttonDisabled]}
            onPress={submit}
            disabled={!month || !day || !year}
          >
            <AppText style={styles.buttonText}>Continue</AppText>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
    card: { width: '100%', maxWidth: 360, paddingHorizontal: spacing.xl },
    title: { ...typography.title, fontSize: 22, color: colors.textPrimary, textAlign: 'center', marginBottom: spacing.sm },
    body: { fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginBottom: spacing.lg, lineHeight: 20 },
    row: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
    input: {
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.md,
      fontSize: 16,
      backgroundColor: colors.surfaceSolid,
      color: colors.textPrimary,
      textAlign: 'center',
    },
    inputSmall: { flex: 1 },
    inputLarge: { flex: 1.6 },
    button: {
      backgroundColor: colors.accent,
      borderRadius: radii.sm,
      paddingVertical: spacing.md,
      alignItems: 'center',
    },
    buttonDisabled: { opacity: 0.5 },
    buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
    error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
  });
}
