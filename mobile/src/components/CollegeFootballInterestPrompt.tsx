import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import AppText from './AppText';
import { useCollegeInterest } from '../context/CollegeInterestContext';
import { useThemeMode } from '../context/ThemeModeContext';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * One-time, non-intrusive "Do you follow college football?" ask (coridian_:
 * "don't make it overbearing"). Deliberately an inline card in the screen's
 * normal scroll content, NOT a Modal/overlay — it never blocks anything
 * below it and a single tap anywhere (Yes, No, or the dismiss X) makes it
 * disappear for good (see CollegeInterestContext). Renders nothing once
 * `status` leaves `'unanswered'` (including the initial `'loading'` read),
 * so a returning user never sees so much as a flash of it.
 *
 * Bug fix (coridian_, 2026-09-27): tapping "Yes, I'm in" used to just close
 * the card with no follow-up — the new "College Prospects" row lives one
 * level down in More, which a first-time yes-answer had no way of knowing.
 * Answering yes now takes the user straight there instead of leaving them
 * to go find it themselves; answering no/dismissing still just closes.
 */
export default function CollegeFootballInterestPrompt() {
  const { status, respond, dismiss } = useCollegeInterest();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  if (status !== 'unanswered') return null;

  const handleYes = () => {
    respond(true);
    navigation.navigate('CollegeProspects');
  };

  return (
    <View style={styles.card}>
      <TouchableOpacity
        style={styles.dismiss}
        onPress={dismiss}
        hitSlop={8}
        accessibilityLabel="Dismiss"
      >
        <Ionicons name="close" size={16} color={colors.textTertiary} />
      </TouchableOpacity>
      <View style={styles.textCol}>
        <AppText style={styles.title}>Do you follow college football?</AppText>
        <AppText style={styles.subtitle}>
          Say yes to grade incoming prospects — your scouting joins everyone else's to help shape
          rookie draft-class strength.
        </AppText>
      </View>
      <View style={styles.actions}>
        <TouchableOpacity style={[styles.button, styles.yesButton]} onPress={handleYes}>
          <AppText style={styles.yesButtonText}>Yes, I'm in</AppText>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.button, styles.noButton]} onPress={() => respond(false)}>
          <AppText style={styles.noButtonText}>Not for me</AppText>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.md,
      marginBottom: spacing.md,
    },
    dismiss: { position: 'absolute', top: spacing.sm, right: spacing.sm, zIndex: 1, padding: 2 },
    textCol: { paddingRight: spacing.lg },
    title: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    subtitle: { fontSize: 12, color: colors.textSecondary, marginTop: 3, lineHeight: 17 },
    actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
    button: {
      flex: 1,
      borderRadius: radii.sm,
      paddingVertical: spacing.sm,
      alignItems: 'center',
      justifyContent: 'center',
    },
    yesButton: { backgroundColor: colors.accent },
    yesButtonText: { color: '#fff', fontSize: 13, fontWeight: '700' },
    noButton: { backgroundColor: colors.surfaceSolid, borderWidth: 1, borderColor: colors.border },
    noButtonText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  });
}
