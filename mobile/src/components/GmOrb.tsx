import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Dimensions,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  useWindowDimensions,
  View,
} from 'react-native';
import AppText from './AppText';
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

import AnimatedCard from './AnimatedCard';
import IconCircle from './IconCircle';
import TrajectoryArcs from './TrajectoryArcs';
import { currentLeagueContext, navigationRef } from '../navigation/navigationRef';
import { api } from '../lib/api';
import { setLastLeague } from '../lib/lastLeague';
import { getSeenTradeIdeaCount } from '../lib/tradeHubSeen';
import { ORB_SCRIM_BASE_HEIGHT, ORB_SIZE } from '../lib/orbLayout';
import { useOrbHorizontalFraction } from '../lib/orbPosition';
import { maskShowcaseFields } from '../lib/showcaseMode';
import { supabase } from '../lib/supabase';
import { useThemeMode } from '../context/ThemeModeContext';
import { motion, radii, shadows, spacing, type ThemeColors } from '../theme';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

interface Destination {
  label: string;
  route: string;
  icon: IconName;
  needsLeague?: boolean;
  // Fixed app-wide semantic families, not one arbitrary hue per item:
  // cyan (colors.accent) = core app/GM intelligence/active navigation,
  // green (colors.success) = roster/waiver/positive-action,
  // amber (colors.premium) = draft/trade-capital,
  // purple (colors.violet) = secondary/analytical,
  // red (colors.danger) = alerts only. Drives the icon-circle tint only —
  // the sheet no longer paints a matching rail down the row (see NavRow).
  color: string;
  // One-line "what's here" — real interface copy describing the actual
  // screen, not a data claim. "Matchup" deliberately says "comparison," not
  // "projections": this app has no weekly points-projection data source.
  subtitle: string;
}

// Split into two groups (was one flat 15-item list) so the sheet can render
// LEAGUE and GM TOOLS as distinct labeled sections per coridian_'s "GM Tools
// should plausibly be Trade Hub/Trade Finder/Trade Analyzer/Trade
// Calculator/GM Targets/Draft Center" taxonomy. Every destination below is
// unchanged from the prior single list — same routes, icons, colors,
// subtitles, `needsLeague` — only the grouping and Recap's position (now
// trailing the core group instead of the trade-tool group) changed.
function coreLeagueDestinations(colors: ThemeColors): Destination[] {
  return [
    {
      label: 'League Overview',
      route: 'LeagueDetail',
      icon: 'grid-outline',
      needsLeague: true,
      color: colors.accent,
      subtitle: 'Standings, settings, and league context',
    },
    {
      label: 'Next Move',
      route: 'Dashboard',
      icon: 'flash-outline',
      needsLeague: true,
      color: colors.accent,
      subtitle: 'Personalized insights and recommendations',
    },
    // Alerts was buried last in the list despite being time-sensitive —
    // moved up next to the other "check this now" destinations.
    {
      label: 'Alerts',
      route: 'Alerts',
      icon: 'notifications-outline',
      needsLeague: true,
      color: colors.danger,
      subtitle: 'Injuries, news, and important updates',
    },
    {
      label: 'My Team',
      route: 'MyTeam',
      icon: 'shirt-outline',
      needsLeague: true,
      color: colors.success,
      subtitle: 'Roster, lineup, and team analysis',
    },
    {
      label: 'Matchup',
      route: 'Matchup',
      icon: 'american-football-outline',
      needsLeague: true,
      color: colors.success,
      subtitle: "This week's matchup and comparison",
    },
    {
      label: 'Waivers',
      route: 'Waivers',
      icon: 'swap-horizontal-outline',
      needsLeague: true,
      color: colors.success,
      subtitle: 'Top adds, trends, and free agents',
    },
    {
      label: 'Teams',
      route: 'Teams',
      icon: 'people-circle-outline',
      needsLeague: true,
      color: colors.violet,
      subtitle: 'View and compare league teams',
    },
    {
      label: 'Players',
      route: 'Players',
      icon: 'people-outline',
      needsLeague: true,
      color: colors.violet,
      subtitle: 'Search, rankings, and player insights',
    },
    {
      label: 'Recap',
      route: 'Recap',
      icon: 'newspaper-outline',
      needsLeague: true,
      color: colors.violet,
      subtitle: 'Weekly league recap and stories',
    },
  ];
}

function gmToolsDestinations(colors: ThemeColors): Destination[] {
  return [
    {
      label: 'Trade Hub',
      route: 'TradeHub',
      icon: 'shuffle-outline',
      needsLeague: true,
      color: colors.premium,
      subtitle: 'Trade ideas and negotiation tools',
    },
    {
      label: 'Trade Finder',
      route: 'TradeFinder',
      icon: 'search-outline',
      needsLeague: true,
      color: colors.premium,
      subtitle: 'Pick players to trade, find who wants them',
    },
    {
      label: 'Trade Analyzer',
      route: 'TradeAnalyzer',
      icon: 'git-compare-outline',
      needsLeague: true,
      color: colors.premium,
      subtitle: 'Analyze and compare any trade',
    },
    {
      label: 'Trade Calculator',
      route: 'TradeCalculator',
      icon: 'calculator-outline',
      needsLeague: true,
      color: colors.premium,
      subtitle: 'Quick value comparisons',
    },
    {
      label: 'GM Targets',
      route: 'GmTargets',
      icon: 'bookmark-outline',
      needsLeague: true,
      color: colors.premium,
      subtitle: 'Your saved watchlist',
    },
    {
      label: 'Draft Center',
      route: 'DraftCenter',
      icon: 'albums-outline',
      needsLeague: true,
      color: colors.premium,
      subtitle: 'Picks, order, and draft tools',
    },
  ];
}

function generalDestinations(colors: ThemeColors): Destination[] {
  return [
    { label: 'Home', route: 'Home', icon: 'home-outline', color: colors.accent, subtitle: 'Switch leagues and manage account' },
    { label: 'News', route: 'News', icon: 'globe-outline', color: colors.violet, subtitle: 'Latest NFL news and updates' },
    {
      label: 'Premium',
      route: 'Paywall',
      icon: 'star-outline',
      color: colors.premium,
      subtitle: 'Unlock the full FantasyGM Lab experience',
    },
    {
      label: 'More',
      route: 'More',
      icon: 'ellipsis-horizontal-outline',
      color: colors.textSecondary,
      subtitle: 'Settings, legal, and support',
    },
  ];
}

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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return <IconCircle name={name} color={current ? colors.accent : color} iconSize={17} style={styles.destIconCircle} />;
}

/**
 * Canonical navigation-row component (coridian_'s "ONE canonical
 * navigation-row" ask) — every destination in every group renders through
 * this. No per-row colored rail anymore: the old `borderLeftColor` per
 * destination was exactly the "rainbow of rails" the redesign brief called
 * out as visual noise. Hierarchy now comes from typography + the single
 * cyan active-state treatment (background tint, accent icon/title, CURRENT
 * label) instead of fourteen different border colors down the list.
 */
function NavRow({
  destination,
  isCurrent,
  unreadCount,
  hasNew,
  onPress,
}: {
  destination: Destination;
  isCurrent: boolean;
  unreadCount?: number;
  /** A plain "something changed here" glyph next to the title — for a
   * destination with real new content but no natural count to show (a
   * ready recap, new trade ideas), as opposed to `unreadCount`'s numeric
   * badge (Alerts' actual unread article count). Optional prop on the
   * shared row, never hardcoded to a specific route inside NavRow itself. */
  hasNew?: boolean;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TouchableOpacity
      style={[styles.destRow, isCurrent && styles.destRowCurrent]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={destination.label}
      accessibilityHint={destination.subtitle}
      // Selected state is announced through this, not just the cyan tint —
      // the visible "CURRENT" text label below carries the same information
      // for sighted users too, so it's never color-only either way.
      accessibilityState={{ selected: isCurrent }}
    >
      <DestIcon name={destination.icon} color={destination.color} current={isCurrent} />
      <View style={styles.destTextGroup}>
        <View style={styles.destTitleRow}>
          <AppText style={[styles.destText, isCurrent && styles.destTextCurrent]} numberOfLines={1}>
            {destination.label}
          </AppText>
          {hasNew ? <View style={[styles.newDot, { backgroundColor: destination.color }]} /> : null}
        </View>
        <AppText style={styles.destSubtitle} numberOfLines={1}>
          {destination.subtitle}
        </AppText>
      </View>
      {unreadCount ? (
        <View style={styles.unreadCountBadge}>
          <AppText style={styles.unreadCountBadgeText}>{unreadCount > 9 ? '9+' : unreadCount}</AppText>
        </View>
      ) : null}
      {isCurrent ? (
        <AppText style={styles.destCurrentBadge}>CURRENT</AppText>
      ) : (
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      )}
    </TouchableOpacity>
  );
}

/**
 * Compact section-label group wrapper (coridian_'s "navigation-section
 * component" ask) — one implementation instead of the three copy-pasted
 * `<AppText style={styles.sectionLabel}>` blocks the sheet used to have for
 * League/Switch League/General. Deliberately not SectionHeading (the
 * Dashboard-promoted shared component): SectionHeading pairs an icon with a
 * larger Title Case label to introduce a group of *cards*, which is a
 * different visual job than this sheet's compact all-caps list-group label
 * — forcing SectionHeading in here would fight coridian_'s "compact
 * section-label groups... not large cards" instruction, not satisfy it.
 */
function NavSection({ label, children }: { label: string; children: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View>
      <AppText style={styles.sectionLabel}>{label}</AppText>
      {children}
    </View>
  );
}

/**
 * Compact league-context module (coridian_'s "league-switcher module" ask) —
 * surfaced near the top of the sheet instead of buried mid-list as its own
 * "Switch League" section. Built on AnimatedCard so it reads as a distinct
 * module rather than another plain destination row (per coridian_'s "not
 * styled identically to plain destination rows"), which is also why this is
 * the one place in the sheet that *does* reuse the shared card primitive.
 * Collapsed by default; expands in place to the same radio-row switching UI
 * the sheet always had, calling the exact same `onSwitch` (GmOrb's
 * `switchToLeague`) with no changes to routing/state logic. Hidden bar
 * itself only renders when there's something to show: an open league, or
 * multiple saved leagues to switch between (mirrors the original gating).
 */
function LeagueSwitcher({
  league,
  savedLeagues,
  expanded,
  onToggle,
  onSwitch,
}: {
  league: { leagueId: string; leagueName: string } | null;
  savedLeagues: SavedLeagueRow[];
  expanded: boolean;
  onToggle: () => void;
  onSwitch: (row: SavedLeagueRow) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const hasAlternates = savedLeagues.length > 1;
  const title = league?.leagueName || 'Select a league';

  return (
    <View style={styles.leagueModule}>
      <AnimatedCard
        style={styles.leagueBar}
        onPress={hasAlternates ? onToggle : undefined}
        disabled={!hasAlternates}
        accessibilityRole="button"
        accessibilityLabel={hasAlternates ? `${title}. Switch league.` : title}
        accessibilityState={hasAlternates ? { expanded } : undefined}
      >
        <View style={styles.leagueBarRow}>
          <IconCircle name="trophy-outline" color={colors.accent} size={30} iconSize={15} />
          <View style={styles.leagueBarText}>
            <AppText style={styles.leagueBarTitle} numberOfLines={1}>
              {title}
            </AppText>
            <AppText style={styles.leagueBarCaption}>{hasAlternates ? 'Switch league' : 'Current league'}</AppText>
          </View>
          {hasAlternates ? (
            <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textTertiary} />
          ) : null}
        </View>
      </AnimatedCard>
      {expanded && hasAlternates ? (
        <View style={styles.leagueAltList}>
          {savedLeagues.map((row) => {
            // Never collapsed by name — every real saved_leagues row (keyed
            // by its own `id`/`league_id`) gets its own entry here even when
            // two leagues share a display name; only `league_id` decides
            // which one is "current."
            const active = row.league_id === league?.leagueId;
            return (
              <TouchableOpacity
                key={row.id}
                style={styles.leagueAltRow}
                onPress={() => onSwitch(row)}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
                accessibilityLabel={row.league_name || row.league_id}
              >
                <Ionicons
                  name={active ? 'radio-button-on' : 'radio-button-off'}
                  size={16}
                  color={active ? colors.accent : colors.textTertiary}
                  style={styles.leagueAltRowIcon}
                />
                <AppText style={[styles.leagueAltRowText, active && styles.leagueAltRowTextActive]} numberOfLines={1}>
                  {row.league_name || row.league_id}
                </AppText>
              </TouchableOpacity>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

export default function GmOrb() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [savedLeagues, setSavedLeagues] = useState<SavedLeagueRow[]>([]);
  const [unreadAlertCount, setUnreadAlertCount] = useState(0);
  const [recapReady, setRecapReady] = useState(false);
  const [tradeHubHasNew, setTradeHubHasNew] = useState(false);
  // Collapsed by default every time the sheet opens — see closeSheet, which
  // resets this so a stale expanded state never carries over to the next
  // open.
  const [switcherExpanded, setSwitcherExpanded] = useState(false);
  // This used to clamp bottom to a 100pt ceiling, on the theory that a
  // reported "orb sits mid-screen" bug meant some device was inflating the
  // inset. Measured rawInsets.bottom on a real iPhone (34), an iOS simulator
  // (34), and an Android emulator (48) — never inflated. The actual bug was
  // content sliding underneath a correctly-positioned orb (see
  // useOrbClearance in lib/orbLayout.ts), and coridian_ confirmed that was
  // the same bug from the very first report, not a second one — so the
  // clamp was removed rather than kept "just in case." Left in place, it was
  // a latent bug of its own: the first device with a legitimately larger
  // inset than 100 would get its orb quietly pulled toward the edge.
  const rawInsets = useSafeAreaInsets();
  const insets = { ...rawInsets, bottom: Math.max(rawInsets.bottom, 0) };
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

  // Same "ready and worth a glance" signal Alerts already surfaces as its
  // own recap-ready banner — mirrored here as a plain glyph on the Recap
  // row itself, so the destination list doesn't need opening Alerts first
  // to notice a new recap exists.
  useEffect(() => {
    if (!open || !league) {
      setRecapReady(false);
      return;
    }
    let cancelled = false;
    api
      .getLeagueRecap(league.leagueId)
      .then((result) => {
        if (!cancelled) setRecapReady(Boolean(result.recap && !result.recap.incomplete));
      })
      .catch(() => {
        if (!cancelled) setRecapReady(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- same reasoning
    // as the alert-count effect above: `league` is a fresh object literal
    // every render, only leagueId actually matters.
  }, [open, league?.leagueId]);

  // Same glyph idea as Recap's, for Trade Hub: no server-side "new idea"
  // concept exists (see lib/tradeHubSeen.ts), so this is just "does the
  // live idea count exceed what this device last actually viewed on the
  // Trade Hub screen."
  useEffect(() => {
    if (!open || !league) {
      setTradeHubHasNew(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const [ideas, seenCount] = await Promise.all([
          api.getTradeHubIdeas(league.leagueId),
          getSeenTradeIdeaCount(league.leagueId),
        ]);
        if (!cancelled) setTradeHubHasNew(ideas.ideas.length > seenCount);
      } catch {
        if (!cancelled) setTradeHubHasNew(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- same reasoning
    // as the alert-count effect above: `league` is a fresh object literal
    // every render, only leagueId actually matters.
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
    setSwitcherExpanded(false);
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
        colors={[`${colors.background}00`, `${colors.background}EB`]}
        style={[styles.scrim, { height: ORB_SCRIM_BASE_HEIGHT + insets.bottom }]}
      />
      <View style={[styles.orbWrap, { bottom: insets.bottom + spacing.xs }]}>
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
              {/* The vector brand mark, not the flat app-icon PNG: that PNG
                  is a fully opaque square with its own baked-in dark-navy
                  fill, so it always shows through as a "grey" disc no
                  matter what this circle's own backgroundColor is set to.
                  TrajectoryArcs has no background of its own, so the disc's
                  real backgroundColor (colors.background, matching where
                  the screen's own wash ends) shows through correctly. */}
              <TrajectoryArcs width={34} height={23} />
            </TouchableOpacity>
          </Animated.View>
        </GestureDetector>
      </View>

      {SHOW_ORB_DEBUG_OVERLAY && (
        <View pointerEvents="none" style={[styles.debugOverlay, { top: rawInsets.top + 4 }]}>
          <AppText style={styles.debugOverlayText}>
            win:{Math.round(Dimensions.get('window').height)} rawBottom:{Math.round(rawInsets.bottom)}{' '}
            orbBottomOffset:{Math.round(insets.bottom + spacing.xs)}
          </AppText>
        </View>
      )}

      <Modal visible={visible} transparent animationType="none" onRequestClose={closeSheet}>
        <Pressable style={StyleSheet.absoluteFill} onPress={closeSheet}>
          <Animated.View style={[styles.backdrop, backdropAnimatedStyle]} />
        </Pressable>
        <Animated.View
          style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }, sheetAnimatedStyle]}
        >
          <Pressable
            style={styles.sheetHandleRow}
            onPress={closeSheet}
            accessibilityRole="button"
            accessibilityLabel="Close menu"
          >
            <View style={styles.sheetHandle} />
          </Pressable>
          <AppText style={styles.sheetKicker}>FantasyGM Lab</AppText>
          <AppText style={styles.sheetTitle}>Where to go</AppText>

          <ScrollView contentContainerStyle={styles.sheetContent} showsVerticalScrollIndicator={false}>
            {league || savedLeagues.length > 1 ? (
              <LeagueSwitcher
                league={league}
                savedLeagues={savedLeagues}
                expanded={switcherExpanded}
                onToggle={() => setSwitcherExpanded((prev) => !prev)}
                onSwitch={switchToLeague}
              />
            ) : null}

            {league ? (
              <>
                <NavSection label="League">
                  {coreLeagueDestinations(colors).map((destination) => (
                    <NavRow
                      key={destination.route}
                      destination={destination}
                      isCurrent={destination.route === currentRouteName}
                      unreadCount={destination.route === 'Alerts' ? unreadAlertCount : undefined}
                      hasNew={destination.route === 'Recap' ? recapReady : false}
                      onPress={() => go(destination)}
                    />
                  ))}
                </NavSection>

                <NavSection label="GM Tools">
                  {gmToolsDestinations(colors).map((destination) => (
                    <NavRow
                      key={destination.route}
                      destination={destination}
                      isCurrent={destination.route === currentRouteName}
                      hasNew={destination.route === 'TradeHub' ? tradeHubHasNew : false}
                      onPress={() => go(destination)}
                    />
                  ))}
                </NavSection>
              </>
            ) : (
              <AppText style={styles.sectionNote}>
                Open a league from Home to unlock Players, Waivers, Trade Analyzer, and more.
              </AppText>
            )}

            <NavSection label="General">
              {generalDestinations(colors).map((destination) => (
                <NavRow
                  key={destination.route}
                  destination={destination}
                  isCurrent={destination.route === currentRouteName}
                  onPress={() => go(destination)}
                />
              ))}
            </NavSection>
          </ScrollView>
        </Animated.View>
      </Modal>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
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
    // `background`, not `surface` — the orb sits right where the screen's
    // GridBackground wash ends (bottom of the screen), which is
    // `background`'s own tone (true OLED black in dark mode). `surface` is
    // one step lighter, and now that `background` is pure black (it used to
    // equal `surface`), that one-step difference reads as a visibly grey
    // disc against the black backdrop instead of blending into it.
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadows.orbGlow,
  },
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
    // radii.lg is 0 — a deliberate app-wide "hard edges" brand choice (see
    // theme.ts), not an oversight here. Every other sheet/modal in the app
    // (e.g. LeagueSwitcherHeaderButton's own switcher) shares this same
    // token, so keeping it — rather than giving this one sheet its own
    // rounded corners — is what actually reads as "premium and intentional"
    // instead of "pasted over": consistent with the rest of the app, not an
    // arbitrary one-off.
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingTop: spacing.md,
    paddingHorizontal: spacing.xl,
    maxHeight: '78%',
    ...shadows.sheet,
  },
  sheetHandleRow: { alignItems: 'center', paddingTop: spacing.xs, paddingBottom: spacing.sm },
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
  sheetTitle: { fontSize: 20, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.lg },
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
  // League-context module (LeagueSwitcher) — a distinct card-like surface,
  // deliberately not styled like the plain destRow rows below it.
  leagueModule: { marginBottom: spacing.md },
  leagueBar: { padding: spacing.md },
  leagueBarRow: { flexDirection: 'row', alignItems: 'center' },
  leagueBarText: { flex: 1, marginLeft: spacing.md, marginRight: spacing.sm },
  leagueBarTitle: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  leagueBarCaption: { fontSize: 12, color: colors.textTertiary, marginTop: 1 },
  leagueAltList: {
    marginTop: spacing.xs,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    backgroundColor: colors.surface,
  },
  leagueAltRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  leagueAltRowIcon: { marginRight: spacing.sm },
  leagueAltRowText: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
  leagueAltRowTextActive: { color: colors.accent },
  destRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xs,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  // The one and only active-navigation treatment (coridian_'s "exactly one
  // visual language for active navigation") — a subtle background tint, no
  // per-row rails anymore (see NavRow's docstring).
  destRowCurrent: { backgroundColor: colors.accentMuted },
  destIconCircle: { marginRight: spacing.md },
  destTextGroup: { flex: 1 },
  destTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  newDot: { width: 6, height: 6, borderRadius: 3 },
  destText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  destTextCurrent: { color: colors.accent },
  destSubtitle: { fontSize: 12, color: colors.textTertiary, marginTop: 1 },
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
}
