import React from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AppText from './AppText';
import { useAuth } from '../context/AuthContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { freeLimitNote, type FreeLimitInput } from '../lib/freeLimits';
import { LINK_HIT_SLOP, spacing, typography } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

/**
 * One small line, before a Free account hits a wall: "Free: 2 of 3 GM
 * Targets" plus the one upgrade path. Guests may not buy, so for them the
 * link reads "Create an account" (the Paywall screen shows guests the
 * account step first). Renders nothing for Premium, an unknown plan or when
 * the server sent no limit. Mirrors web-next's FreeLimitNote.
 */
export default function FreeLimitNote(props: Omit<FreeLimitInput, 'isGuest'>) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { isGuest } = useAuth();
  const { colors } = useThemeMode();
  const note = freeLimitNote({ ...props, isGuest });
  if (!note) return null;
  return (
    <View style={styles.row} accessibilityRole="summary">
      <AppText style={[typography.caption, { color: colors.textTertiary }]}>{note.text}</AppText>
      <TouchableOpacity accessibilityRole="button" onPress={() => navigation.navigate('Paywall')} hitSlop={LINK_HIT_SLOP}>
        <AppText style={[typography.caption, styles.cta, { color: colors.premium }]}>{note.ctaLabel} ›</AppText>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
  cta: { fontWeight: '700' },
});
