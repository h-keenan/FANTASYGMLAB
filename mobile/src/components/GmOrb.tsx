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
  useWindowDimensions,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { StackActions } from '@react-navigation/routers';

import IconCircle from './IconCircle';
import { currentLeagueContext, navigationRef } from '../navigation/navigationRef';
import { api } from '../lib/api';
import { setLastLeague } from '../lib/lastLeague';
import { ORB_INSET_CEILING, ORB_SCRIM_BASE_HEIGHT, ORB_SIZE } from '../lib/orbLayout';
import { useOrbHorizontalFraction } from '../lib/orbPosition';
import { maskShowcaseFields } from '../lib/showcaseMode';
import { supabase } from '../lib/supabase';
import { colors, motion, radii, shadows, spacing } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

interface Destination {
  label: string;
  route: string;
  icon: IconName;
  needsLeague?: boolean;
  // Grouped by function rather than each getting its own unique hue — one
  // color per family (nav/roster/trade/scouting/urgent) reads as "this
  // section has an identity" without turning the menu into a rainbow, per
  // coridian_'s "distinct colors but don't overdo it" direction.
  color: string;
}

const LEAGUE_DESTINATIONS: Destination[] = [
  { label: 'League Overview', route: 'LeagueDetail', icon: 'grid-outline', needsLeague: true, color: colors.accent },
  { label: 'Next Move', route: 'Dashboard', icon: 'flash-outline', needsLeague: true, color: colors.accent },
  // Alerts was buried last in the list despite being time-sensitive —
  // moved up next to the other "check this now" destinations.
  { label: 'Alerts', route: 'Alerts', icon: 'notifications-outline', needsLeague: true, color: colors.danger },
  { label: 'My Team', route: 'MyTeam', icon: 'shirt-outline', needsLeague: true, color: colors.success },
  {
    label: 'Matchup',
    route: 'Matchup',
    icon: 'american-football-outline',
    needsLeague: true,
    color: colors.success,
  },
  { label: 'Waivers', route: 'Waivers', icon: 'swap-horizontal-outline', needsLeague: true, color: colors.success },
  { label: 'Teams', route: 'Teams', icon: 'people-circle-outline', needsLeague: true, color: colors.violet },
  { label: 'Players', route: 'Players', icon: 'people-outline', needsLeague: true, color: colors.violet },
  { label: 'Trade Hub', route: 'TradeHub', icon: 'shuffle-outline', needsLeague: true, color: colors.premium },
  {
    label: 'Trade Analyzer',
    route: 'TradeAnalyzer',
    icon: 'git-compare-outline',
    needsLeague: true,
    color: colors.premium,
  },
  {
    label: 'Trade Calculator',
    route: 'TradeCalculator',
    icon: 'calculator-outline',
    needsLeague: true,
    color: colors.premium,
  },
  { label: 'GM Targets', route: 'GmTargets', icon: 'bookmark-outline', needsLeague: true, color: colors.premium },
  { label: 'Draft Center', route: 'DraftCenter', icon: 'albums-outline', needsLeague: true, color: colors.premium },
  { label: 'Recap', route: 'Recap', icon: 'newspaper-outline', needsLeague: true, color: colors.violet },
];

const GENERAL_DESTINATIONS: Destination[] = [
  { label: 'Home', route: 'Home', icon: 'home-outline', color: colors.accent },
  { label: 'News', route: 'News', icon: 'globe-outline', color: colors.violet },
  { label: 'Premium', route: 'Paywall', icon: 'star-outline', color: colors.premium },
  { label: 'More', route: 'More', icon: 'ellipsis-horizontal-outline', color: colors.textSecondary },
];

interface SavedLeagueRow {
  id: string;
  league_id: string;
  league_name: string;
}

const CLOSE_MS = 260;

// Kept behind this flag rather than deleted outright — the clearance fix in
// lib/orbLayout.ts hasn't been confirmed in the field yet, and if it turns
// out incomplete, this is the fastest way to see why. Remove once a fresh
// device screenshot confirms the fix. Not gated on __DEV__: this needs to be
// visible in a release/TestFlight build, which is exactly where __DEV__ is
// false. Set EXPO_PUBLIC_SHOW_ORB_DEBUG_OVERLAY=1 at build time to enable.
const SHOW_ORB_DEBUG_OVERLAY = process.env.EXPO_PUBLIC_SHOW_ORB_DEBUG_OVERLAY === '1';

/**
 * The floating "GM" brand-mark button + destination sheet — the mobile
 * counterpart to the web app's gm_orb_floating_trigger/render_mobile_destination_sheet
 * (modules/brand_identity.py, app.py). Rendered once, globally, so every
 * screen gets the same always-available navigation affordance instead of
 * each screen inventing its own per-page tool row. Defaults to bottom-center
 * since it's the app's primary global navigation, reachable by either thumb,
 * and doesn't collide with left-aligned avatars or right-aligned values in
 * list rows — but that's a default, not a mandate: touch-and-hold lets
 * someone drag it to whichever side suits their own grip, persisted per
 * device (see orbPosition.ts). Horizontal movement only; vertical position
 * always stays anchored to the safe-area bottom via useOrbClearance, so a
 * dragged orb can never collide with content the way an orb that moved
 * vertically could (see PR #514's history).
 */
/** Icon-in-colored-circle treatment (pulled from the FGL design reference
 * sheet) instead of a bare icon — in a 14-row destination list, a soft
 * colored backdrop per icon reads as a scannable landmark, not just a
 * decoration next to the label. */
function DestIcon({ name, color, current }: { name: IconName; color: string; current: boolean }) {
  return <IconCircle name={name} color={current ? colors.accent : color} iconSize={17} style={styles.destIconCircle} />;
}

export default function GmOrb() {
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [savedLeagues, setSavedLeagues] = useState<SavedLeagueRow[]>([]);
  const [unreadAlertCount, setUnreadAlertCount] = useState(0);
  const rawInsets = useSafeAreaInsets();
  // Purely precautionary — no evidence this has ever actually fired. This
  // was originally written to defend against an inflated bottom inset,
  // which was the leading theory for a reported bug where the orb appeared
  // to sit mid-screen. That bug turned out to be content sliding underneath
  // a correctly-positioned orb (see useOrbClearance in lib/orbLayout.ts),
  // not the orb itself moving — confirmed by measuring rawInsets.bottom on
  // a real iPhone (34), an iOS simulator (34), and an Android emulator (48),
  // none of them inflated. If you're reading this because you found an
  // inset-inflation bug on some device, that would be new evidence this
  // clamp doesn't currently have — nothing observed so far justifies it.
  const safeBottom = Math.min(Math.max(rawInsets.bottom, 0), ORB_INSET_CEILING);
  const insets = { ...rawInsets, bottom: safeBottom };
  const league = open ? currentLeagueContext() : null;
  const currentRouteName = open && navigationRef.isReady() ? navigationRef.getCurrentRoute()?.name : undefined;
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sheetY = useSharedValue(400);
  const backdropOpacity = useSharedValue(0);
  const orbScale = useSharedValue(1);
  const orbOpacity = useSharedValue(1);

  // Tap-and-hold to reposition — horizontal only (see orbPosition.ts for
  // why). `activateAfterLongPress` means a quick tap still falls through to
  // the TouchableOpacity's onPress below instead of starting a drag.
  const { width: screenWidth } = useWindowDimensions();
  const [horizontalFraction, setHorizontalFraction] = useOrbHorizontalFraction();
  const dragX = useSharedValue(0);
  const dragStartX = useSharedValue(0);

  // How far the orb's center can move from screen-center before it would
  // sit under a notch/rounded corner or off the horizontal safe area.
  // Recomputed every render (not cached) so rotation and iPad split-view/
  // Stage Manager resizing re-clamp automatically instead of trusting a
  // stale bound — deliberately not memoized for the same reason the
  // persisted value below is a fraction, not a pixel offset.
  const leftBound = Math.min(-1, insets.left + ORB_SIZE / 2 + spacing.sm - screenWidth / 2);
  const rightBound = Math.max(1, screenWidth - insets.right - ORB_SIZE / 2 - spacing.sm - screenWidth / 2);

  useEffect(() => {
    dragX.value = horizontalFraction >= 0 ? horizontalFraction * rightBound : horizontalFraction * -leftBound;
  }, [horizontalFraction, leftBound, rightBound]);

  const dragGesture = Gesture.Pan()
    .activateAfterLongPress(350)
    .onStart(() => {
      dragStartX.value = dragX.value;
      runOnJS(Haptics.impactAsync)(Haptics.ImpactFeedbackStyle.Medium);
    })
    .onUpdate((event) => {
      const next = dragStartX.value + event.translationX;
      dragX.value = Math.min(rightBound, Math.max(leftBound, next));
    })
    .onEnd(() => {
      const finalX = dragX.value;
      const fraction = finalX >= 0 ? finalX / rightBound : finalX / -leftBound;
      runOnJS(setHorizontalFraction)(fraction);
    });

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    supabase
      .from('saved_leagues')
      .select('id, league_id, league_name')
      .then(({ data }) => {
        // Straight from Supabase, so authorizedRequest's showcase masking
        // never sees these — mask the league switcher's names here too.
        if (!cancelled && data) setSavedLeagues(maskShowcaseFields(data as SavedLeagueRow[]));
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open || !league) {
      setUnreadAlertCount(0);
      return;
    }
    let cancelled = false;
    api
      .getLeagueAlerts(league.leagueId, 12)
      .then((result) => {
        if (!cancelled) setUnreadAlertCount(result.items.filter((item) => !item.read).length);
      })
      .catch(() => {
        if (!cancelled) setUnreadAlertCount(0);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `league` is a
    // fresh object literal from currentLeagueContext() every render (not
    // memoized); depending on it directly would refetch every render while
    // the sheet is open. leagueId is the only part that actually matters.
  }, [open, league?.leagueId]);

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
    // The orb is the app's only cross-section navigation affordance, so a
    // session hops between the same hub screens repeatedly (Home -> Waivers
    // -> TradeHub -> MyTeam -> Waivers -> ...). Plain `navigate()` in
    // React Navigation 7 only reuses an existing screen instance when it's
    // already the current route; otherwise it pushes a new one, so the back
    // stack would grow without bound. `popTo` pops back to an existing
    // instance of the destination if one is already on the stack, or
    // replaces the current screen with it if not - the stack never grows
    // past one screen per orb hop.
    if (!destination.needsLeague) {
      navigationRef.dispatch(StackActions.popTo(destination.route));
      return;
    }
    if (!league) return;
    navigationRef.dispatch(StackActions.popTo(destination.route, league));
  };

  const switchToLeague = (row: SavedLeagueRow) => {
    closeSheet();
    const target = { leagueId: row.league_id, leagueName: row.league_name || 'League' };
    void setLastLeague(target);
    if (navigationRef.isReady()) {
      navigationRef.dispatch(StackActions.popTo('LeagueDetail', target));
    }
  };

  const orbAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: orbScale.value }, { translateX: dragX.value }],
    opacity: orbOpacity.value,
  }));
  const backdropAnimatedStyle = useAnimatedStyle(() => ({ opacity: backdropOpacity.value }));
  const sheetAnimatedStyle = useAnimatedStyle(() => ({ transform: [{ translateY: sheetY.value }] }));

  return (
    <>
      <LinearGradient
        pointerEvents="none"
        colors={['rgba(13,17,23,0)', 'rgba(13,17,23,0.92)']}
        style={[styles.scrim, { height: ORB_SCRIM_BASE_HEIGHT + insets.bottom }]}
      />
      <View style={[styles.orbWrap, { bottom: insets.bottom + spacing.md }]}>
        <GestureDetector gesture={dragGesture}>
          <Animated.View style={orbAnimatedStyle}>
            <TouchableOpacity
              style={styles.orb}
              onPress={openSheet}
              accessibilityLabel="Open GM menu"
              accessibilityHint="Double tap to open. Touch and hold, then drag, to move it."
              activeOpacity={0.85}
              // ORB_SIZE (48) already meets both platforms' stated minimum
              // touch target (44pt iOS, 48dp Android) with zero margin —
              // hitSlop gives real headroom above the bare minimum rather
              // than sitting exactly on the line.
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Image source={require('../../assets/icon.png')} style={styles.orbImage} />
            </TouchableOpacity>
          </Animated.View>
        </GestureDetector>
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
                      <DestIcon name={destination.icon} color={destination.color} current={isCurrent} />
                      <Text style={[styles.destText, isCurrent && styles.destTextCurrent]} numberOfLines={1}>
                        {destination.label}
                      </Text>
                      {destination.route === 'Alerts' && unreadAlertCount > 0 ? (
                        <View style={styles.unreadCountBadge}>
                          <Text style={styles.unreadCountBadgeText}>
                            {unreadAlertCount > 9 ? '9+' : unreadAlertCount}
                          </Text>
                        </View>
                      ) : null}
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
                  <DestIcon name={destination.icon} color={destination.color} current={isCurrent} />
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
  destIconCircle: { marginRight: spacing.md },
  destText: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  destTextCurrent: { color: colors.accent },
  destCurrentBadge: { fontSize: 10, fontWeight: '700', color: colors.accent, letterSpacing: 0.6 },
  unreadCountBadge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 4,
    backgroundColor: colors.danger,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.xs,
  },
  unreadCountBadgeText: { fontSize: 10, fontWeight: '700', color: '#fff' },
});
