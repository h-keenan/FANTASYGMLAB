import React, { useEffect, useRef, useState } from 'react';
import {
  Dimensions,
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';

import { currentLeagueContext, navigationRef } from '../navigation/navigationRef';
import { setLastLeague } from '../lib/lastLeague';
import { supabase } from '../lib/supabase';
import { colors, motion, radii, shadows, spacing } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

interface Destination {
  label: string;
  route: string;
  icon: IconName;
  needsLeague?: boolean;
}

const LEAGUE_DESTINATIONS: Destination[] = [
  { label: 'League Overview', route: 'LeagueDetail', icon: 'grid-outline', needsLeague: true },
  { label: 'Next Move', route: 'Dashboard', icon: 'flash-outline', needsLeague: true },
  { label: 'Teams', route: 'Teams', icon: 'people-circle-outline', needsLeague: true },
  { label: 'Players', route: 'Players', icon: 'people-outline', needsLeague: true },
  { label: 'GM Targets', route: 'GmTargets', icon: 'bookmark-outline', needsLeague: true },
  { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline', needsLeague: true },
  { label: 'Trade Hub', route: 'TradeHub', icon: 'shuffle-outline', needsLeague: true },
  { label: 'Trade Analyzer', route: 'TradeAnalyzer', icon: 'git-compare-outline', needsLeague: true },
  { label: 'Trade Calculator', route: 'TradeCalculator', icon: 'calculator-outline', needsLeague: true },
  { label: 'Recap', route: 'Recap', icon: 'newspaper-outline', needsLeague: true },
  { label: 'Alerts', route: 'Alerts', icon: 'notifications-outline', needsLeague: true },
];

const GENERAL_DESTINATIONS: Destination[] = [
  { label: 'Home', route: 'Home', icon: 'home-outline' },
  { label: 'News', route: 'News', icon: 'globe-outline' },
  { label: 'Premium', route: 'Paywall', icon: 'star-outline' },
  { label: 'More', route: 'More', icon: 'ellipsis-horizontal-outline' },
];

interface SavedLeagueRow {
  id: string;
  league_id: string;
  league_name: string;
}

const ORB_SIZE = 64;
const CLOSE_MS = 260;

// TEMPORARY — remove once the real-device orb-position bug (reported by
// coridian_/ocyws, not reproducible on an iOS simulator) is confirmed fixed.
// Surfaces the exact numbers a screenshot can't show, so a reporter without a
// debugger can hand back the one measurement that actually settles it: is
// insets.bottom inflated (a native SDK setting additionalSafeAreaInsets and
// never clearing it), or is it normal and the bug lives elsewhere.
//
// Deliberately NOT gated on __DEV__ — the bug this instruments only shows up
// on a real device / release build, which is exactly where __DEV__ is false.
// Gated on a build-time env var instead so it defaults OFF (including in a
// normal TestFlight build) unless someone explicitly opts a build into it —
// set EXPO_PUBLIC_SHOW_ORB_DEBUG_OVERLAY=1 when building the diagnostic build.
const SHOW_ORB_DEBUG_OVERLAY = process.env.EXPO_PUBLIC_SHOW_ORB_DEBUG_OVERLAY === '1';

/**
 * The floating "GM" brand-mark button + destination sheet — the mobile
 * counterpart to the web app's gm_orb_floating_trigger/render_mobile_destination_sheet
 * (modules/brand_identity.py, app.py). Rendered once, globally, so every
 * screen gets the same always-available navigation affordance instead of
 * each screen inventing its own per-page tool row. Bottom-center (not
 * bottom-left/right) since it's the app's primary global navigation,
 * reachable by either thumb, and doesn't collide with left-aligned avatars
 * or right-aligned values in list rows.
 */
export default function GmOrb() {
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [savedLeagues, setSavedLeagues] = useState<SavedLeagueRow[]>([]);
  const rawInsets = useSafeAreaInsets();
  // Belt-and-suspenders clamp — kept even though instrumented measurements
  // (RootNavigator's wrapper, useSafeAreaFrame, and this hook) all agreed the
  // insets were never actually wrong. The real bug was mixing a layout-
  // affecting inline `bottom` with a Reanimated animated style on the same
  // Animated.View below; that combination can resolve position against a
  // stale frame under Fabric. Fixed by keeping `orbWrap`'s positioning on a
  // plain View and moving the scale/opacity animation to an inner
  // Animated.View that carries no layout props of its own.
  //
  // Ceiling raised from 40 to 100: an Android emulator with gesture navigation
  // measured a legitimate rawBottom of 48, which the old 40 ceiling was
  // clipping 8dp short of the intended position — and 48 is just one stock
  // image, not the full range of OEM nav-bar variants. Rather than chase each
  // newly-measured device one bump at a time, 100 is chosen with real margin:
  // the clamp only stays useful as a diagnostic (able to rule out inset
  // inflation as the cause of the reported ~65-70%-down symptom) as long as
  // the resulting bottom offset stays under ~198 — see the arithmetic in
  // PR #513/#510. 100 clears every legitimate inset seen so far with room to
  // spare, while leaving ~98pt of headroom below where the clamp would start
  // masking the actual bug instead of ruling it out.
  const safeBottom = Math.min(Math.max(rawInsets.bottom, 0), 100);
  const insets = { ...rawInsets, bottom: safeBottom };
  const league = open ? currentLeagueContext() : null;
  const currentRouteName = open && navigationRef.isReady() ? navigationRef.getCurrentRoute()?.name : undefined;
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sheetY = useSharedValue(400);
  const backdropOpacity = useSharedValue(0);
  const orbScale = useSharedValue(1);
  const orbOpacity = useSharedValue(1);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    supabase
      .from('saved_leagues')
      .select('id, league_id, league_name')
      .then(({ data }) => {
        if (!cancelled && data) setSavedLeagues(data as SavedLeagueRow[]);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const openSheet = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setVisible(true);
    setOpen(true);
    sheetY.value = withSpring(0, motion.sheetSpring);
    backdropOpacity.value = withTiming(0.55, { duration: 220 });
    orbScale.value = withTiming(0.9, { duration: 180 });
    orbOpacity.value = withTiming(0, { duration: 180 });
  };

  const closeSheet = () => {
    setOpen(false);
    sheetY.value = withTiming(400, { duration: CLOSE_MS });
    backdropOpacity.value = withTiming(0, { duration: 200 });
    orbScale.value = withTiming(1, { duration: 200 });
    orbOpacity.value = withTiming(1, { duration: 200 });
    closeTimer.current = setTimeout(() => setVisible(false), CLOSE_MS);
  };

  const go = (destination: Destination) => {
    closeSheet();
    if (!navigationRef.isReady()) return;
    // Destinations are a data-driven list (not a single statically-known
    // route), so this dispatches dynamically rather than through the
    // strongly-typed `navigate` overloads.
    const navigate = navigationRef.navigate as (name: string, params?: object) => void;
    if (destination.needsLeague) {
      if (!league) return;
      navigate(destination.route, league);
    } else {
      navigate(destination.route);
    }
  };

  const switchToLeague = (row: SavedLeagueRow) => {
    closeSheet();
    const target = { leagueId: row.league_id, leagueName: row.league_name || 'League' };
    void setLastLeague(target);
    if (navigationRef.isReady()) {
      (navigationRef.navigate as (name: string, params?: object) => void)('LeagueDetail', target);
    }
  };

  const orbAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: orbScale.value }],
    opacity: orbOpacity.value,
  }));
  const backdropAnimatedStyle = useAnimatedStyle(() => ({ opacity: backdropOpacity.value }));
  const sheetAnimatedStyle = useAnimatedStyle(() => ({ transform: [{ translateY: sheetY.value }] }));

  return (
    <>
      <LinearGradient
        pointerEvents="none"
        colors={['rgba(13,17,23,0)', 'rgba(13,17,23,0.92)']}
        style={[styles.scrim, { height: 112 + insets.bottom }]}
      />
      <View style={[styles.orbWrap, { bottom: insets.bottom + spacing.md }]}>
        <Animated.View style={orbAnimatedStyle}>
          <TouchableOpacity
            style={styles.orb}
            onPress={openSheet}
            accessibilityLabel="Open GM menu"
            activeOpacity={0.85}
          >
            <Image source={require('../../assets/icon.png')} style={styles.orbImage} />
          </TouchableOpacity>
        </Animated.View>
      </View>

      {SHOW_ORB_DEBUG_OVERLAY && (
        <View pointerEvents="none" style={[styles.debugOverlay, { top: rawInsets.top + 4 }]}>
          <Text style={styles.debugOverlayText}>
            win:{Math.round(Dimensions.get('window').height)} rawBottom:{Math.round(rawInsets.bottom)}{' '}
            clampedBottom:{Math.round(insets.bottom)} orbBottomOffset:{Math.round(insets.bottom + spacing.md)}
          </Text>
        </View>
      )}

      <Modal visible={visible} transparent animationType="none" onRequestClose={closeSheet}>
        <Pressable style={StyleSheet.absoluteFill} onPress={closeSheet}>
          <Animated.View style={[styles.backdrop, backdropAnimatedStyle]} />
        </Pressable>
        <Animated.View
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }, sheetAnimatedStyle]}
        >
          <Pressable style={styles.sheetHandleRow} onPress={closeSheet}>
            <View style={styles.sheetHandle} />
          </Pressable>
          <Text style={styles.sheetKicker}>FantasyGM Lab</Text>
          <Text style={styles.sheetTitle}>Where to go</Text>

          <ScrollView contentContainerStyle={styles.sheetContent}>
            {league ? (
              <>
                <Text style={styles.sectionLabel}>{league.leagueName}</Text>
                {LEAGUE_DESTINATIONS.map((destination) => {
                  const isCurrent = destination.route === currentRouteName;
                  return (
                    <TouchableOpacity
                      key={destination.route}
                      style={[styles.destRow, isCurrent && styles.destRowCurrent]}
                      onPress={() => go(destination)}
                    >
                      <Ionicons
                        name={destination.icon}
                        size={20}
                        color={isCurrent ? colors.accent : colors.textSecondary}
                        style={styles.destIcon}
                      />
                      <Text style={[styles.destText, isCurrent && styles.destTextCurrent]} numberOfLines={1}>
                        {destination.label}
                      </Text>
                      {isCurrent ? (
                        <Text style={styles.destCurrentBadge}>CURRENT</Text>
                      ) : (
                        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                      )}
                    </TouchableOpacity>
                  );
                })}
              </>
            ) : (
              <Text style={styles.sectionNote}>
                Open a league from Home to unlock Players, Waivers, Trade Analyzer, and more.
              </Text>
            )}

            {savedLeagues.length > 1 ? (
              <>
                <Text style={styles.sectionLabel}>Switch League</Text>
                {savedLeagues.map((row) => (
                  <TouchableOpacity key={row.id} style={styles.row} onPress={() => switchToLeague(row)}>
                    <Ionicons
                      name={row.league_id === league?.leagueId ? 'radio-button-on' : 'radio-button-off'}
                      size={18}
                      color={row.league_id === league?.leagueId ? colors.accent : colors.textTertiary}
                      style={styles.rowIcon}
                    />
                    <Text style={styles.rowText} numberOfLines={1}>
                      {row.league_name || row.league_id}
                    </Text>
                  </TouchableOpacity>
                ))}
              </>
            ) : null}

            <Text style={styles.sectionLabel}>General</Text>
            {GENERAL_DESTINATIONS.map((destination) => {
              const isCurrent = destination.route === currentRouteName;
              return (
                <TouchableOpacity
                  key={destination.route}
                  style={[styles.destRow, isCurrent && styles.destRowCurrent]}
                  onPress={() => go(destination)}
                >
                  <Ionicons
                    name={destination.icon}
                    size={20}
                    color={isCurrent ? colors.accent : colors.textSecondary}
                    style={styles.destIcon}
                  />
                  <Text style={[styles.destText, isCurrent && styles.destTextCurrent]} numberOfLines={1}>
                    {destination.label}
                  </Text>
                  {isCurrent ? (
                    <Text style={styles.destCurrentBadge}>CURRENT</Text>
                  ) : (
                    <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                  )}
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </Animated.View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  scrim: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 5,
  },
  orbWrap: {
    position: 'absolute',
    left: '50%',
    marginLeft: -ORB_SIZE / 2,
    width: ORB_SIZE,
    height: ORB_SIZE,
    zIndex: 6,
    ...shadows.orb,
  },
  debugOverlay: {
    position: 'absolute',
    left: 8,
    right: 8,
    zIndex: 100,
    backgroundColor: 'rgba(0,0,0,0.75)',
    borderRadius: 6,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  debugOverlayText: {
    color: '#00FF88',
    fontSize: 11,
    fontFamily: 'Courier',
    textAlign: 'center',
  },
  orb: {
    width: ORB_SIZE,
    height: ORB_SIZE,
    borderRadius: ORB_SIZE / 2,
    overflow: 'hidden',
    borderWidth: 1.5,
    borderColor: 'rgba(0,212,255,0.55)',
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadows.orbGlow,
  },
  orbImage: { width: ORB_SIZE * 1.15, height: ORB_SIZE * 1.15 },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000',
  },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: colors.backgroundElevated,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingTop: spacing.sm,
    paddingHorizontal: spacing.xl,
    maxHeight: '78%',
    ...shadows.sheet,
  },
  sheetHandleRow: { alignItems: 'center', paddingVertical: spacing.xs },
  sheetHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.borderStrong,
  },
  sheetKicker: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.accent,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  sheetTitle: { fontSize: 20, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.md },
  sheetContent: { paddingBottom: spacing.md },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  sectionNote: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowIcon: { marginRight: spacing.sm },
  rowText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
  destRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    borderLeftWidth: 2,
    borderLeftColor: 'transparent',
  },
  destRowCurrent: { borderLeftColor: colors.accent, backgroundColor: colors.accentMuted },
  destIcon: { marginRight: spacing.md, width: 20 },
  destText: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  destTextCurrent: { color: colors.accent },
  destCurrentBadge: { fontSize: 10, fontWeight: '700', color: colors.accent, letterSpacing: 0.6 },
});
