import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

interface Props {
  title: string;
  description: string;
}

/**
 * The mobile equivalent of web's render_premium_lock — shown wherever a
 * Free account has content actually withheld server-side (not just a
 * decorative upsell), so seeing this card always means there's real content
 * behind it. Tapping goes straight to Paywall, matching web's direct
 * begin_upgrade_flow behavior (no intermediate explanation screen).
 */
export default function PremiumLock({ title, description }: Props) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  return (
    <AnimatedCard style={styles.card} onPress={() => navigation.navigate('Paywall')}>
      <View style={styles.iconWrap}>
        <Ionicons name="lock-closed" size={18} color={colors.premium} />
      </View>
      <View style={styles.textGroup}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.description}>{description}</Text>
      </View>
      <View style={styles.cta}>
        <Text style={styles.ctaText}>Upgrade</Text>
        <Ionicons name="chevron-forward" size={14} color={colors.premium} />
      </View>
    </AnimatedCard>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderWidth: 1,
    borderColor: `${colors.premium}40`,
    backgroundColor: `${colors.premium}14`,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radii.sm,
    backgroundColor: `${colors.premium}26`,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
  },
  textGroup: { flex: 1, marginRight: spacing.sm },
  title: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  description: { fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 },
  cta: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  ctaText: { fontSize: 13, fontWeight: '700', color: colors.premium },
});
