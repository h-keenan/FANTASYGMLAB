import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import AppText from '../components/AppText';
import SectionHeading from '../components/SectionHeading';
import GridBackground from '../components/GridBackground';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import IconCircle from '../components/IconCircle';
import { api, type PushCategory } from '../lib/api';
import { openStoreSubscriptionSettings } from '../lib/storeSubscriptions';
import { activeTrialEnd } from '../lib/revenuecat';
import { trialEndLabel } from '../lib/freeTrial';
import { syncPushToken } from '../lib/pushNotifications';
import { useOrbClearance } from '../lib/orbLayout';
import { isShowcaseModeAvailable } from '../lib/showcaseMode';
import { trackOnboarding } from '../lib/onboardingAnalytics';
import { radii, spacing, type ThemeColors, scrim } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { currentLeagueContext } from '../navigation/navigationRef';
import { useAuth } from '../context/AuthContext';
import { useCollegeInterest } from '../context/CollegeInterestContext';
import { useDensity, type UiDensity } from '../context/DensityContext';
import { useExperienceLevel } from '../context/ExperienceLevelContext';
import type { ExperienceLevel } from '../lib/experienceCopy';
import { useThemeMode, type ThemeMode } from '../context/ThemeModeContext';
import { useShowcaseMode } from '../context/ShowcaseModeContext';
import Input from '../components/Input';
import ReferralCard from '../components/ReferralCard';
import Toggle from '../components/Toggle';
import ModalFormCard, { ModalFormActions, ModalFormHint, ModalFormTitle } from '../components/ModalFormCard';

type Props = NativeStackScreenProps<RootStackParamList, 'More'>;
type IconName = React.ComponentProps<typeof IconCircle>['name'];

const LEGAL_ITEMS: Array<{ pageKey: string; label: string; icon: IconName }> = [
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

// Onboarding's "How much dynasty experience do you have?" answer, changeable
// here later. Copy only (lib/experienceCopy.ts); an unanswered account shows
// as Advanced because that's exactly how it behaves.
const EXPERIENCE_OPTIONS: Array<{ value: ExperienceLevel; label: string; description: string }> = [
  { value: 'beginner', label: 'Beginner', description: 'Plain-language explanations of terms like value, tier and trade verdicts' },
  { value: 'advanced', label: 'Advanced', description: 'The standard terse copy' },
];

const THEME_OPTIONS: Array<{ value: ThemeMode; label: string; description: string }> = [
  { value: 'dark', label: 'Night', description: 'OLED black — always dark' },
  { value: 'light', label: 'Day', description: 'Glacier ice white — always light' },
  { value: 'auto', label: 'Auto', description: "Match this device's system setting" },
];

const PUSH_CATEGORY_LABELS: Array<{ value: PushCategory; label: string; description: string }> = [
  { value: 'top_priority', label: 'Top Priority moves', description: 'The single most urgent recommendation for your roster' },
  { value: 'watch', label: 'Watch items', description: 'Worth knowing, not urgent' },
  { value: 'recap', label: 'Weekly recaps', description: 'When a new League Recap is ready' },
  { value: 'injury', label: 'Injury updates', description: 'A status change on your own roster (Questionable, Out, etc.)' },
  { value: 'team_situation', label: 'Team Situation reminder', description: 'A one-time nudge to set rebuilding, competing, or balanced' },
  { value: 'trade_followup', label: 'Trade follow-ups', description: 'Asking whether a trade you shared actually happened' },
  { value: 'lineup_lock', label: 'Lineup lock reminders', description: 'An empty slot or an injured starter shortly before kickoff' },
  { value: 'waiver_reminder', label: 'Waiver reminders', description: 'Before waivers process, only when you have a clear need' },
];

export default function MoreScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const [sendingTestPush, setSendingTestPush] = useState(false);
  const { density, setDensity } = useDensity();
  const { level: experienceLevel, setLevel: setExperienceLevel } = useExperienceLevel();
  const { mode: themeMode, setMode: setThemeMode, colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [pushCategories, setPushCategories] = useState<Record<PushCategory, boolean> | null>(null);
  const [updatingCategory, setUpdatingCategory] = useState<PushCategory | null>(null);
  const { deleteAccount, session, isGuest, convertGuestToAccount } = useAuth();
  const [trialEnd, setTrialEnd] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    void activeTrialEnd().then((end) => {
      if (!cancelled) setTrialEnd(end);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const [deleting, setDeleting] = useState(false);
  const [guestUpgradeOpen, setGuestUpgradeOpen] = useState(false);
  const [guestUpgradeEmail, setGuestUpgradeEmail] = useState('');
  const [guestUpgradePassword, setGuestUpgradePassword] = useState('');
  const [guestUpgradeSubmitting, setGuestUpgradeSubmitting] = useState(false);
  const [guestUpgradeError, setGuestUpgradeError] = useState<string | null>(null);
  const [guestUpgradeNotice, setGuestUpgradeNotice] = useState<string | null>(null);
  const { showcaseMode, setShowcaseMode } = useShowcaseMode();
  const { status: collegeInterestStatus, respond: respondToCollegeInterest } = useCollegeInterest();
  // Dev/founder accounts only (lib/showcaseMode.ts allowlist) — the row
  // doesn't exist for anyone else, so there's nothing for a normal user to
  // stumble into.
  const showcaseAvailable = isShowcaseModeAvailable(session?.user?.email, session?.user?.app_metadata);

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

  const [exporting, setExporting] = useState(false);
  const onExportData = async () => {
    setExporting(true);
    try {
      const result = await api.exportMyData();
      const json = JSON.stringify(result, null, 2);
      // Share the export as an actual .json file, not a raw-text message.
      // A real account's export (13 tables, potentially years of Decision
      // Memory/scouting rows) can run well past what Share.share's text
      // `message` reliably delivers — Android's Binder IPC caps an Intent's
      // extras around 1MB, so a large export silently failed to hand off
      // to Messages/Mail/etc. with no distinguishable error. Writing to a
      // file and sharing *that* (same expo-sharing pattern the Player/Trade/
      // Recap share cards already use for their screenshot PNGs) has no
      // such size ceiling and gives the user a real file they can save,
      // which is also just a better shape for "my data" than a text blob.
      const canShareFile = await Sharing.isAvailableAsync();
      if (canShareFile) {
        const file = new File(Paths.cache, `fantasydesk-my-data-${Date.now()}.json`);
        file.create();
        file.write(json);
        await Sharing.shareAsync(file.uri, {
          mimeType: 'application/json',
          UTI: 'public.json',
          dialogTitle: 'My FantasyDesk data',
        });
      } else {
        // Rare fallback (file sharing unavailable on this device) — same
        // text-message share this screen used before.
        await Share.share({ title: 'My FantasyDesk data', message: json });
      }
    } catch {
      Alert.alert('Could not export your data', 'Please try again in a moment.');
    } finally {
      setExporting(false);
    }
  };

  // Compliant cancellation path for IAP is the platform's own subscription
  // settings, not a custom in-app flow (Apple/Google require this) — this
  // just saves the "your device's account settings" instruction on the
  // Paywall from being a manual hunt.
  const onManageSubscription = openStoreSubscriptionSettings;

  const onOpenTeamStance = () => {
    const league = currentLeagueContext();
    if (!league) {
      Alert.alert('Select a league first', 'Open a league from Home, then come back to set your Team Situation.');
      return;
    }
    navigation.navigate('GmPlan', { ...league, initialTab: 'overview' });
  };

  // League-scoped entry points (Live Draft, Guess the Player leaderboard)
  // resolve the league the user last opened, same as Team Situation above.
  const onOpenLeagueScreen = (screen: 'LiveDraft' | 'GuessThePlayerLeaderboard', purpose: string) => {
    const league = currentLeagueContext();
    if (!league) {
      Alert.alert('Select a league first', `Open a league from Home, then come back ${purpose}.`);
      return;
    }
    navigation.navigate(screen, league);
  };

  const closeGuestUpgrade = () => {
    setGuestUpgradeOpen(false);
    setGuestUpgradeEmail('');
    setGuestUpgradePassword('');
    setGuestUpgradeError(null);
    setGuestUpgradeNotice(null);
  };

  // Fix 3 (welcome/signup audit): upgrades the CURRENT guest session in
  // place (see AuthContext.convertGuestToAccount) — the connected league
  // and everything else already tied to this guest's id simply stays
  // connected, nothing to re-enter.
  const onSubmitGuestUpgrade = async () => {
    setGuestUpgradeError(null);
    setGuestUpgradeNotice(null);
    setGuestUpgradeSubmitting(true);
    const result = await convertGuestToAccount(guestUpgradeEmail, guestUpgradePassword);
    setGuestUpgradeSubmitting(false);
    if (result.error) {
      setGuestUpgradeError(result.error);
      return;
    }
    setGuestUpgradeNotice('Check your email to confirm your account. Your league stays connected once you do.');
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
    <View style={styles.root}>
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingTop: headerHeight, paddingBottom: orbClearance }]}
      >
        <SectionHeading title="Preferences" />
        <AppText style={styles.groupCaption}>Density</AppText>
        <View style={styles.optionRow}>
          {DENSITY_OPTIONS.map((option) => (
            <OptionCard
              key={option.value}
              label={option.label}
              description={option.description}
              active={density === option.value}
              onPress={() => setDensity(option.value)}
            />
          ))}
        </View>
        <AppText style={styles.groupCaption}>Explanations</AppText>
        <View style={styles.optionRow}>
          {EXPERIENCE_OPTIONS.map((option) => (
            <OptionCard
              key={option.value}
              label={option.label}
              description={option.description}
              active={(experienceLevel ?? 'advanced') === option.value}
              onPress={() => setExperienceLevel(option.value)}
            />
          ))}
        </View>
        <AppText style={styles.groupCaption}>Theme</AppText>
        <View style={styles.optionRow}>
          {THEME_OPTIONS.map((option) => (
            <OptionCard
              key={option.value}
              label={option.label}
              description={option.description}
              active={themeMode === option.value}
              onPress={() => setThemeMode(option.value)}
            />
          ))}
        </View>

        <SectionHeading title="Your Team" topGap={16} />
        <AnimatedCard style={styles.groupCard}>
          <SettingsRow
            icon="compass-outline"
            iconColor={colors.accent}
            label="Team Situation"
            description="Declare Rebuilding / Competing / Balanced and manage protected players"
            onPress={onOpenTeamStance}
            showDivider
          />
          <SettingsRow
            icon="swap-horizontal-outline"
            iconColor={colors.accent}
            label="Trade History"
            description="Trades you've shared and confirmed, plus how they've worked out so far"
            onPress={() => navigation.navigate('TradeHistory')}
            showDivider
          />
          <SettingsRow
            icon="timer-outline"
            iconColor={colors.premium}
            label="Live Draft"
            description="Real-time pick recommendations while your Sleeper draft is running (Premium)"
            onPress={() => onOpenLeagueScreen('LiveDraft', 'to use Live Draft')}
            showDivider
          />
          <SettingsRow
            icon="trophy-outline"
            iconColor={colors.accent}
            label="Guess the Player Leaderboard"
            description="Daily-game streaks among leaguemates on FantasyDesk"
            onPress={() => onOpenLeagueScreen('GuessThePlayerLeaderboard', 'to see the leaderboard')}
            showDivider={false}
          />
        </AnimatedCard>

        {collegeInterestStatus === 'yes' ? (
          <>
            <SectionHeading title="Scouting" topGap={16} />
            <AnimatedCard style={styles.groupCard}>
              <SettingsRow
                icon="school-outline"
                iconColor={colors.accent}
                label="College Prospects"
                description="Grade incoming prospects and follow your own watchlist"
                onPress={() => navigation.navigate('CollegeProspects')}
                showDivider={false}
              />
            </AnimatedCard>
          </>
        ) : null}

        {/* Discoverability audit (2026-09-26): saying "Not for me" (or just
            dismissing) the one-time Dashboard prompt permanently hid College
            Prospects with no way back — the only revisit path in the whole
            app was reinstalling. "Replay intro tutorial" below already
            establishes the pattern of a small always-available link back to a
            one-time choice; this mirrors it for the college-football opt-in
            instead of inventing a new mechanism. */}
        {collegeInterestStatus === 'no' ? (
          <>
            <SectionHeading title="Scouting" topGap={16} />
            <AnimatedCard style={styles.groupCard}>
              <SettingsRow
                icon="school-outline"
                iconColor={colors.textSecondary}
                label="Follow college football?"
                description="You said this wasn't for you — tap to turn on prospect scouting"
                onPress={() => respondToCollegeInterest(true)}
                showDivider={false}
              />
            </AnimatedCard>
          </>
        ) : null}

        <SectionHeading title="Notifications" topGap={16} />
        <AnimatedCard style={styles.groupCard}>
          <SettingsRow
            icon="notifications-outline"
            iconColor={colors.accent}
            label="Send test notification"
            onPress={onSendTestPush}
            disabled={sendingTestPush}
            right={sendingTestPush ? <ActivityIndicator size="small" color={colors.accent} /> : undefined}
            showDivider={Boolean(pushCategories)}
          />
          {pushCategories
            ? PUSH_CATEGORY_LABELS.map((item, index) => (
                <SettingsRow
                  key={item.value}
                  label={item.label}
                  description={item.description}
                  showDivider={index < PUSH_CATEGORY_LABELS.length - 1}
                  right={
                    <Toggle
                      value={pushCategories[item.value]}
                      onValueChange={(next) => onTogglePushCategory(item.value, next)}
                      disabled={updatingCategory === item.value}
                      label={item.label}
                    />
                  }
                />
              ))
            : null}
        </AnimatedCard>

        <SectionHeading title="About" topGap={16} />
        <AnimatedCard style={styles.groupCard}>
          <SettingsRow
            icon="school-outline"
            iconColor={colors.violet}
            label="How We Evaluate"
            onPress={() => navigation.navigate('HowWeEvaluate')}
            showDivider
          />
          <SettingsRow
            icon="play-circle-outline"
            iconColor={colors.accent}
            label="Replay the tour"
            onPress={() => {
              trackOnboarding('replayed');
              navigation.navigate('Onboarding', { replay: true });
            }}
            showDivider={false}
          />
        </AnimatedCard>

        {showcaseAvailable ? (
          <>
            <SectionHeading title="Developer" topGap={16} />
            <AnimatedCard style={styles.groupCard}>
              <SettingsRow
                icon="videocam-outline"
                iconColor={colors.premium}
                label="Privacy mode"
                description="Hides manager, team and league names, avatars and email for screenshots. Display only; player and football data are untouched."
                showDivider={false}
                right={
                  <Toggle value={showcaseMode} onValueChange={setShowcaseMode} tone="premium" label="Privacy mode" />
                }
              />
            </AnimatedCard>
          </>
        ) : null}

        {/* Hidden dev path: long-press (1.5s) opens the design-system reference. */}
        <Pressable accessibilityRole="button" onLongPress={() => navigation.navigate('Design')} delayLongPress={1500}>
          <SectionHeading title="Legal" topGap={16} />
        </Pressable>
        <AnimatedCard style={styles.groupCard}>
          {LEGAL_ITEMS.map((item, index) => (
            <SettingsRow
              key={item.pageKey}
              icon={item.icon}
              iconColor={colors.textSecondary}
              label={item.label}
              onPress={() => navigation.navigate('LegalPage', { pageKey: item.pageKey })}
              showDivider={index < LEGAL_ITEMS.length - 1}
            />
          ))}
        </AnimatedCard>

        {isGuest ? null : (
          <View style={styles.referralWrap}>
            <ReferralCard />
          </View>
        )}

        <SectionHeading title="Account" topGap={16} />
        <AnimatedCard style={styles.groupCard}>
          {isGuest ? (
            <SettingsRow
              icon="person-add-outline"
              iconColor={colors.accent}
              label="Create account"
              description="Keep this league connected — no need to re-enter your Sleeper info"
              onPress={() => setGuestUpgradeOpen(true)}
              showDivider
            />
          ) : null}
          <SettingsRow
            icon="card-outline"
            iconColor={colors.textSecondary}
            label="Manage Subscription"
            description={trialEndLabel(trialEnd) || undefined}
            onPress={onManageSubscription}
            showDivider
          />
          <SettingsRow
            icon="download-outline"
            iconColor={colors.textSecondary}
            label="Export My Data"
            onPress={onExportData}
            disabled={exporting}
            right={exporting ? <ActivityIndicator size="small" color={colors.textSecondary} /> : undefined}
            showDivider={false}
          />
        </AnimatedCard>

        {/* Destructive action gets its own visually distinct surface
            (danger border/tint) rather than sitting in the neutral Account
            card above — Magna Carta §17: destructive actions should look
            distinct, not just be a row with red text among routine ones. */}
        <AnimatedCard style={styles.dangerCard}>
          <SettingsRow
            icon="trash-outline"
            iconColor={colors.danger}
            label="Delete account"
            danger
            onPress={onDeleteAccount}
            disabled={deleting}
            right={deleting ? <ActivityIndicator size="small" color={colors.danger} /> : null}
            showDivider={false}
          />
        </AnimatedCard>
      </ScrollView>

      <ModalFormCard visible={guestUpgradeOpen} onClose={closeGuestUpgrade}>
        <ModalFormTitle>Create account</ModalFormTitle>
        <ModalFormHint>Your connected league carries over automatically — nothing to re-enter.</ModalFormHint>
        <Input
          style={styles.modalInput}
          placeholder="Email"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          textContentType="username"
          autoComplete="email"
          value={guestUpgradeEmail}
          onChangeText={setGuestUpgradeEmail}
          editable={!guestUpgradeSubmitting}
        />
        <Input
          style={styles.modalInput}
          placeholder="Password"
          secureTextEntry
          textContentType="newPassword"
          autoComplete="new-password"
          value={guestUpgradePassword}
          onChangeText={setGuestUpgradePassword}
          editable={!guestUpgradeSubmitting}
        />
        {guestUpgradeError ? <AppText style={styles.guestUpgradeError}>{guestUpgradeError}</AppText> : null}
        {guestUpgradeNotice ? <AppText style={styles.guestUpgradeNotice}>{guestUpgradeNotice}</AppText> : null}
        <ModalFormActions
          onCancel={closeGuestUpgrade}
          cancelDisabled={guestUpgradeSubmitting}
          confirmLabel="Create account"
          onConfirm={onSubmitGuestUpgrade}
          confirmDisabled={!guestUpgradeEmail || !guestUpgradePassword}
          confirmLoading={guestUpgradeSubmitting}
        />
      </ModalFormCard>
    </View>
  );
}

/**
 * One selectable choice card (Density/Explanations/Theme) — a compact label + supporting
 * description, active state rendered as an accent-tinted fill + border
 * (same "illuminated" language SegmentedTabBar uses for its active segment)
 * rather than a plain border-color swap. Kept local: SegmentedTabBar itself
 * only supports a bare label per option, no room for the description text
 * these two choosers need, so this is a genuine variant rather than a
 * duplicate of an existing shared component (§47).
 */
function OptionCard({
  label,
  description,
  active,
  onPress,
}: {
  label: string;
  description: string;
  active: boolean;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TouchableOpacity accessibilityRole="button"
      style={[styles.optionCard, active && styles.optionCardActive]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <AppText style={[styles.optionLabel, active && styles.optionLabelActive]}>{label}</AppText>
      <AppText style={styles.optionDescription}>{description}</AppText>
    </TouchableOpacity>
  );
}

/**
 * One settings-list row — icon-in-circle (or none for indented toggle rows
 * that already share a parent icon), label, optional description, optional
 * right-side control (chevron/switch/spinner), optional bottom divider.
 * Mirrors the AlertRow/LineupRow local-row convention already established
 * on AlertsScreen/MyTeamScreen for rows living inside a `groupCard`.
 */
function SettingsRow({
  icon,
  iconColor,
  label,
  description,
  onPress,
  disabled,
  right,
  showDivider,
  danger,
}: {
  icon?: IconName;
  iconColor?: string;
  label: string;
  description?: string;
  onPress?: () => void;
  disabled?: boolean;
  right?: React.ReactNode;
  showDivider: boolean;
  danger?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Color-system audit (2026-09-25): `disabled` previously reached
  // TouchableOpacity only — it blocked the tap but changed nothing visible,
  // so a disabled row was indistinguishable from an enabled one (the
  // "disabled elements still look intentionally disabled" dark/light-mode
  // check both brief's checklist and Magna Carta §48 call for). Label/icon
  // now switch to the dedicated `textDisabled` token when disabled.
  const content = (
    <View style={[styles.row, showDivider && styles.rowDivider]}>
      <View style={styles.labelGroup}>
        {icon ? (
          <IconCircle
            name={icon}
            color={disabled ? colors.textDisabled : iconColor ?? colors.textSecondary}
            style={styles.icon}
          />
        ) : null}
        <View style={styles.labelTextGroup}>
          <AppText style={[danger ? styles.dangerLabel : styles.label, disabled && styles.labelDisabled]}>
            {label}
          </AppText>
          {description ? <AppText style={styles.rowDescription}>{description}</AppText> : null}
        </View>
      </View>
      {right !== undefined ? right : onPress ? <AppText style={styles.chevron}>{'›'}</AppText> : null}
    </View>
  );
  if (!onPress) return content;
  return (
    <TouchableOpacity accessibilityRole="button" onPress={onPress} disabled={disabled} activeOpacity={0.7}>
      {content}
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.lg },
    sectionLabel: {
      fontSize: 12,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
      marginTop: spacing.lg,
      marginBottom: spacing.sm,
    },
    sectionLabelFirst: { marginTop: 0 },
    groupCaption: {
      fontSize: 12,
      fontWeight: '600',
      color: colors.textSecondary,
      marginBottom: spacing.xs,
    },
    // One grouped surface per section with hairline dividers between rows,
    // instead of a separately bordered/backgrounded row per item — Magna
    // Carta §12, same `groupCard` pattern MyTeamScreen/AlertsScreen use.
    groupCard: { padding: spacing.md, paddingVertical: 0 },
    referralWrap: { marginTop: 16 },
    dangerCard: {
      padding: spacing.md,
      paddingVertical: 0,
      marginTop: spacing.md,
      borderColor: colors.danger,
      backgroundColor: colors.dangerMuted,
    },
    row: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingVertical: spacing.md,
      gap: spacing.md,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    labelGroup: { flexDirection: 'row', alignItems: 'center', flexShrink: 1, flex: 1 },
    icon: { marginRight: spacing.md },
    labelTextGroup: { flexShrink: 1 },
    label: { fontSize: 15, color: colors.textPrimary, flexShrink: 1 },
    labelDisabled: { color: colors.textDisabled },
    dangerLabel: { fontSize: 15, fontWeight: '600', color: colors.danger, flexShrink: 1 },
    chevron: { fontSize: 20, color: colors.textSecondary },
    rowDescription: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    optionRow: {
      flexDirection: 'row',
      gap: spacing.sm,
      marginBottom: spacing.md,
    },
    optionCard: {
      flex: 1,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.sm,
    },
    optionCardActive: {
      borderColor: colors.accent,
      backgroundColor: colors.accentMuted,
    },
    optionLabel: {
      fontSize: 14,
      fontWeight: '700',
      color: colors.textPrimary,
      marginBottom: 2,
    },
    optionLabelActive: {
      color: colors.accent,
    },
    optionDescription: {
      fontSize: 12,
      color: colors.textSecondary,
    },
    modalInput: { marginBottom: spacing.sm },
    guestUpgradeError: { fontSize: 12, color: colors.danger, marginTop: spacing.xs, lineHeight: 16 },
    guestUpgradeNotice: { fontSize: 12, color: colors.success, marginTop: spacing.xs, lineHeight: 16 },
  });
}
