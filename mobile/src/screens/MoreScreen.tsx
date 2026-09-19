import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Switch, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import IconCircle from '../components/IconCircle';
import { api, type PushCategory } from '../lib/api';
import { syncPushToken } from '../lib/pushNotifications';
import { useOrbClearance } from '../lib/orbLayout';
import { isShowcaseModeAvailable } from '../lib/showcaseMode';
import { colors, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { useAuth } from '../context/AuthContext';
import { useDensity, type UiDensity } from '../context/DensityContext';
import { useShowcaseMode } from '../context/ShowcaseModeContext';

type Props = NativeStackScreenProps<RootStackParamList, 'More'>;

const LEGAL_ITEMS: Array<{ pageKey: string; label: string; icon: React.ComponentProps<typeof IconCircle>['name'] }> = [
  { pageKey: 'about_disclaimer', label: 'About / Disclaimer', icon: 'information-circle-outline' },
  { pageKey: 'terms', label: 'Terms of Use', icon: 'document-text-outline' },
  { pageKey: 'privacy', label: 'Privacy Policy', icon: 'shield-checkmark-outline' },
  { pageKey: 'subscription_terms', label: 'Subscription Terms', icon: 'card-outline' },
  { pageKey: 'no_affiliation', label: 'No-Affiliation Disclaimer', icon: 'alert-circle-outline' },
];

const DENSITY_OPTIONS: Array<{ value: UiDensity; label: string; description: string }> = [
  { value: 'guided', label: 'Guided', description: 'Show the reasoning behind every recommendation' },
  { value: 'compact', label: 'Compact', description: 'Just the calls — hide the explanation text' },
];

const PUSH_CATEGORY_LABELS: Array<{ value: PushCategory; label: string; description: string }> = [
  { value: 'top_priority', label: 'Top Priority moves', description: 'The single most urgent recommendation for your roster' },
  { value: 'watch', label: 'Watch items', description: 'Worth knowing, not urgent' },
  { value: 'recap', label: 'Weekly recaps', description: 'When a new League Recap is ready' },
  { value: 'injury', label: 'Injury updates', description: 'A status change on your own roster (Questionable, Out, etc.)' },
];

export default function MoreScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const [sendingTestPush, setSendingTestPush] = useState(false);
  const { density, setDensity } = useDensity();
  const [pushCategories, setPushCategories] = useState<Record<PushCategory, boolean> | null>(null);
  const [updatingCategory, setUpdatingCategory] = useState<PushCategory | null>(null);
  const { deleteAccount, session } = useAuth();
  const [deleting, setDeleting] = useState(false);
  const { showcaseMode, setShowcaseMode } = useShowcaseMode();
  // Dev/founder accounts only (lib/showcaseMode.ts allowlist) — the row
  // doesn't exist for anyone else, so there's nothing for a normal user to
  // stumble into.
  const showcaseAvailable = isShowcaseModeAvailable(session?.user?.email);

  useEffect(() => {
    let cancelled = false;
    api
      .getPushPreferences()
      .then((result) => {
        if (!cancelled && result.ok) setPushCategories(result.categories);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const onTogglePushCategory = async (category: PushCategory, nextEnabled: boolean) => {
    if (!pushCategories) return;
    const previous = pushCategories;
    setPushCategories({ ...pushCategories, [category]: nextEnabled });
    setUpdatingCategory(category);
    try {
      const result = await api.updatePushPreference(category, nextEnabled);
      if (result.ok) {
        setPushCategories(result.categories);
      } else {
        setPushCategories(previous);
      }
    } catch {
      setPushCategories(previous);
    } finally {
      setUpdatingCategory(null);
    }
  };

  const onSendTestPush = async () => {
    setSendingTestPush(true);
    try {
      await syncPushToken();
      const result = await api.sendTestPush();
      if (result.ok) {
        Alert.alert('Test notification sent', 'It should arrive shortly.');
      } else if (result.reason === 'no_registered_tokens') {
        Alert.alert(
          'No device registered yet',
          "We couldn't find a push token for this device. Make sure notifications are allowed for this app in Settings, then try again.",
        );
      } else {
        Alert.alert('Could not send test notification', 'Please try again in a moment.');
      }
    } catch {
      Alert.alert('Could not send test notification', 'Please try again in a moment.');
    } finally {
      setSendingTestPush(false);
    }
  };

  const onDeleteAccount = () => {
    Alert.alert(
      'Delete account?',
      'This permanently deletes your account and all data — saved leagues, GM Targets, trade history. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            setDeleting(true);
            const { error } = await deleteAccount();
            setDeleting(false);
            if (error) {
              Alert.alert('Could not delete account', 'Please try again in a moment.');
            }
            // On success there's nothing else to do here — clearing the
            // session flips RootNavigator back to the Auth stack on its own.
          },
        },
      ],
    );
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={{ paddingBottom: orbClearance }}>
      <AppText style={styles.sectionLabel}>Display</AppText>
      <View style={styles.densityRow}>
        {DENSITY_OPTIONS.map((option) => {
          const active = density === option.value;
          return (
            <TouchableOpacity
              key={option.value}
              style={[styles.densityOption, active && styles.densityOptionActive]}
              onPress={() => setDensity(option.value)}
            >
              <AppText style={[styles.densityOptionLabel, active && styles.densityOptionLabelActive]}>
                {option.label}
              </AppText>
              <AppText style={styles.densityOptionDescription}>{option.description}</AppText>
            </TouchableOpacity>
          );
        })}
      </View>

      <AppText style={styles.sectionLabel}>Notifications</AppText>
      <TouchableOpacity style={styles.row} onPress={onSendTestPush} disabled={sendingTestPush}>
        <View style={styles.labelGroup}>
          <IconCircle name="notifications-outline" color={colors.accent} style={styles.icon} />
          <AppText style={styles.label}>Send test notification</AppText>
        </View>
        {sendingTestPush ? <ActivityIndicator size="small" color={colors.accent} /> : <AppText style={styles.chevron}>{'›'}</AppText>}
      </TouchableOpacity>

      {pushCategories
        ? PUSH_CATEGORY_LABELS.map((item) => (
            <View key={item.value} style={styles.row}>
              <View style={styles.labelGroup}>
                <View style={styles.toggleTextGroup}>
                  <AppText style={styles.label}>{item.label}</AppText>
                  <AppText style={styles.toggleDescription}>{item.description}</AppText>
                </View>
              </View>
              <Switch
                value={pushCategories[item.value]}
                onValueChange={(next) => onTogglePushCategory(item.value, next)}
                disabled={updatingCategory === item.value}
                trackColor={{ true: colors.accent, false: colors.border }}
              />
            </View>
          ))
        : null}

      <AppText style={styles.sectionLabel}>About</AppText>
      <TouchableOpacity style={styles.row} onPress={() => navigation.navigate('HowWeEvaluate')}>
        <View style={styles.labelGroup}>
          <IconCircle name="school-outline" color={colors.violet} style={styles.icon} />
          <AppText style={styles.label}>How We Evaluate</AppText>
        </View>
        <AppText style={styles.chevron}>{'›'}</AppText>
      </TouchableOpacity>

      {showcaseAvailable ? (
        <>
          <AppText style={styles.sectionLabel}>Developer</AppText>
          <View style={styles.row}>
            <View style={styles.labelGroup}>
              <IconCircle name="videocam-outline" color={colors.premium} style={styles.icon} />
              <View style={styles.toggleTextGroup}>
                <AppText style={styles.label}>Showcase mode</AppText>
                <AppText style={styles.toggleDescription}>
                  Replaces every team name, league name, owner name and username with
                  stand-ins so screen recordings stay anonymous. Player and football data
                  are untouched.
                </AppText>
              </View>
            </View>
            <Switch
              value={showcaseMode}
              onValueChange={setShowcaseMode}
              trackColor={{ true: colors.premium, false: colors.border }}
            />
          </View>
        </>
      ) : null}

      <AppText style={styles.sectionLabel}>Legal</AppText>
      {LEGAL_ITEMS.map((item) => (
        <TouchableOpacity
          key={item.pageKey}
          style={styles.row}
          onPress={() => navigation.navigate('LegalPage', { pageKey: item.pageKey })}
        >
          <View style={styles.labelGroup}>
            <IconCircle name={item.icon} color={colors.textSecondary} style={styles.icon} />
            <AppText style={styles.label}>{item.label}</AppText>
          </View>
          <AppText style={styles.chevron}>{'›'}</AppText>
        </TouchableOpacity>
      ))}

      <AppText style={styles.sectionLabel}>Account</AppText>
      <TouchableOpacity style={styles.row} onPress={onDeleteAccount} disabled={deleting}>
        <View style={styles.labelGroup}>
          <IconCircle name="trash-outline" color={colors.danger} style={styles.icon} />
          <AppText style={styles.dangerLabel}>Delete account</AppText>
        </View>
        {deleting ? <ActivityIndicator size="small" color={colors.danger} /> : null}
      </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xs,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surface,
  },
  labelGroup: { flexDirection: 'row', alignItems: 'center', flexShrink: 1 },
  // Icon-in-colored-circle per row (same disc GM Orb's destination sheet
  // uses) — More is the app's other menu-like list, so it gets the same
  // scannable landmark per row. Sections keep distinct tints (accent for
  // actions, violet for learning, neutral for legal, danger for delete)
  // rather than one accent everywhere.
  icon: { marginRight: spacing.md },
  label: { fontSize: 16, color: colors.textPrimary, flexShrink: 1 },
  dangerLabel: { fontSize: 16, color: colors.danger, flexShrink: 1 },
  chevron: { fontSize: 20, color: colors.textSecondary },
  toggleTextGroup: { flexShrink: 1, paddingRight: spacing.md },
  toggleDescription: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  densityRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.md,
    gap: spacing.sm,
  },
  densityOption: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
  },
  densityOptionActive: {
    borderColor: colors.accent,
  },
  densityOptionLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  densityOptionLabelActive: {
    color: colors.accent,
  },
  densityOptionDescription: {
    fontSize: 12,
    color: colors.textSecondary,
  },
});
