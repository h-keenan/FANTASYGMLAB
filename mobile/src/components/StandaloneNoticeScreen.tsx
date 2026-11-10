import React from 'react';
import { Image, Pressable, StyleSheet, Text, View, useColorScheme } from 'react-native';

import { darkColors, lightColors, radii, spacing } from '../theme';

/**
 * Full-screen notice that depends on NO app context/provider, so it still
 * renders when a provider (or the navigator) is what crashed: used by the root
 * error boundary and the "Update required" gate. Colors come from the shared
 * theme tokens, chosen by the OS color scheme.
 */
export default function StandaloneNoticeScreen({
  title,
  body,
  actionLabel,
  onAction,
  detail,
}: {
  title: string;
  body: string;
  actionLabel: string;
  onAction: () => void;
  detail?: string;
}) {
  const scheme = useColorScheme();
  const colors = scheme === 'light' ? lightColors : darkColors;
  return (
    <View style={[styles.root, { backgroundColor: colors.background }]}>
      <Image
        source={require('../../assets/brand-mark.png')}
        style={[styles.mark, { tintColor: colors.textPrimary }]}
        resizeMode="contain"
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      />
      <Text accessibilityRole="header" style={[styles.title, { color: colors.textPrimary }]}>
        {title}
      </Text>
      <Text style={[styles.body, { color: colors.textSecondary }]}>{body}</Text>
      {detail ? <Text style={[styles.detail, { color: colors.textTertiary }]}>{detail}</Text> : null}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={actionLabel}
        onPress={onAction}
        style={[styles.button, { backgroundColor: colors.accent }]}
      >
        <Text style={[styles.buttonText, { color: colors.onAccent }]}>{actionLabel}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl, gap: spacing.md },
  mark: { width: 120, height: 56, marginBottom: spacing.md },
  title: { fontSize: 20, fontWeight: '700', textAlign: 'center' },
  body: { fontSize: 15, lineHeight: 22, textAlign: 'center', maxWidth: 360 },
  detail: { fontSize: 12, textAlign: 'center' },
  button: { marginTop: spacing.md, paddingHorizontal: spacing.xl, minHeight: 48, borderRadius: radii.md, alignItems: 'center', justifyContent: 'center' },
  buttonText: { fontSize: 16, fontWeight: '700' },
});
