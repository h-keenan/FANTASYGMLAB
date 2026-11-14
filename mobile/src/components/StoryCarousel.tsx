import React, { useEffect, useId, useMemo, useReducer, useRef, useSyncExternalStore, type ReactNode } from 'react';
import { Animated, Easing, PanResponder, Pressable, StyleSheet, View } from 'react-native';
import { GestureDetector } from 'react-native-gesture-handler';
import Reanimated, { useAnimatedStyle, useReducedMotion, useSharedValue } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { SheetModal, useSheetDismissGesture } from './SwipeDismissSheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { EASE, MOTION_MS } from '../lib/motion';
import { overlayStack } from '../lib/overlayStack';
import { storyInitial, storyIsLast, storyReducer, storySegmentFill, storySwipeAction, storyTapAction } from '../lib/storyCarousel';
import { spacing, type ThemeColors } from '../theme';

export interface StoryHeader {
  eyebrow: string;
  /** Heavy ~30px title; wraps to a second line, never ellipsized. */
  title: string;
  subtitle?: string | null;
}

export interface StoryPage {
  key: string;
  /** Short kicker above the page ("Result", "Around the league"). */
  label: string;
  /** Optional big page header (eyebrow + bold title + one-line subtitle) in the fixed top zone; replaces the small kicker. */
  header?: StoryHeader;
  /** The page itself: a hero number and at most three supporting items. No scrolling. */
  content: ReactNode;
  /** Page footer (a CTA). The last page's footer is the story's finish action. */
  footer?: ReactNode;
}

/**
 * The shared full-screen story carousel, twin of web-next's components/ui/StoryCarousel.tsx: one glanceable
 * page at a time, progress segments on top, a close X, swipe or tap the left/right of the screen. A full-screen
 * Modal, safe-area aware, a short slide that is off under reduced motion. `hidden` hides the modal (the
 * caller keeps the page state) while a player card is up: iOS cannot present two native modals, so the
 * card shows alone and the story comes back on the same page when it closes. See docs/ui-patterns.md.
 */
export default function StoryCarousel({
  title,
  pages,
  onClose,
  initialIndex = 0,
  testID = 'story-carousel',
}: {
  title: string;
  pages: StoryPage[];
  onClose: () => void;
  initialIndex?: number;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const insets = useSafeAreaInsets();
  const reduceMotion = useReducedMotion();
  const [state, dispatch] = useReducer(storyReducer, undefined, () => storyInitial(pages.length, initialIndex));
  const slide = useRef(new Animated.Value(1)).current;
  const id = useId();
  const widthRef = useRef(0);
  const stateRef = useRef(state);
  stateRef.current = state;

  // THE overlay stack (lib/overlayStack.ts): one pop-up at a time. A player card opened from a page hides this
  // Modal (iOS cannot present two) and its Back returns to the same page: the page state lives here, not in the Modal.
  useSyncExternalStore(overlayStack.subscribe, overlayStack.version, overlayStack.version);
  useEffect(() => {
    overlayStack.open({ id, kind: 'sheet', title, dismiss: onClose });
    return () => overlayStack.close(id);
  }, [id, title, onClose]);
  const hidden = overlayStack.isHidden(id);

  useEffect(() => {
    dispatch({ type: 'count', count: pages.length });
  }, [pages.length]);

  useEffect(() => {
    if (state.direction === 'none' || reduceMotion) return;
    slide.setValue(0);
    Animated.timing(slide, { toValue: 1, duration: MOTION_MS.base, easing: Easing.bezier(...EASE.out), useNativeDriver: true }).start();
  }, [state.index, state.direction, reduceMotion, slide]);

  // Swipe down to leave, like every sheet (shared gesture, lib/sheetGesture.ts): the whole card follows the finger,
  // shrinks and fades, then closes through the same path as the X (overlayStack.closeAll). It only claims a vertical
  // pull; the horizontal page swipe and the tap zones are untouched. Pages never scroll, so there is no content to
  // conflict with.
  const pullY = useSharedValue(0);
  const screenHeight = useSharedValue(0);
  const { gesture: pullGesture } = useSheetDismissGesture({ translateY: pullY, sheetHeight: screenHeight, onDismiss: () => overlayStack.closeAll(), enabled: !hidden });
  const pullStyle = useAnimatedStyle(() => {
    const progress = screenHeight.value > 0 ? Math.min(1, Math.max(0, pullY.value / screenHeight.value)) : 0;
    return { opacity: 1 - 0.55 * progress, transform: [{ translateY: pullY.value }, { scale: 1 - 0.1 * progress }] };
  });

  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => Math.abs(g.dx) > 12 && Math.abs(g.dx) > Math.abs(g.dy),
        onPanResponderRelease: (_e, g) => {
          const swipe = storySwipeAction(g.dx, g.dy);
          if (swipe) dispatch({ type: swipe });
        },
      }),
    [],
  );

  const page = pages[Math.min(state.index, pages.length - 1)];
  if (!page) return null;
  const last = storyIsLast(state);
  const dir = state.direction === 'prev' ? -1 : 1;
  const translateX = slide.interpolate({ inputRange: [0, 1], outputRange: [28 * dir, 0] });

  return (
    <SheetModal visible={!hidden} transparent={false} animationType="fade" onRequestClose={() => overlayStack.back?.() ?? onClose()} statusBarTranslucent>
      <GestureDetector gesture={pullGesture}>
      <Reanimated.View
        style={[styles.root, { paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, spacing.md) }, pullStyle]}
        testID={testID}
        accessibilityViewIsModal
        onLayout={(e) => (screenHeight.value = e.nativeEvent.layout.height)}
      >
        <View style={styles.top}>
          <View style={styles.progress} accessibilityRole="progressbar" accessibilityLabel={`Page ${state.index + 1} of ${state.count}`}>
            {pages.map((p, i) => (
              <PressableScale key={p.key} style={styles.segHit} onPress={() => dispatch({ type: 'goto', index: i })} accessibilityRole="button" accessibilityLabel={`Go to ${p.label}`}>
                <View style={styles.seg}>
                  <View style={[styles.segFill, { opacity: storySegmentFill(i, state.index) }]} />
                </View>
              </PressableScale>
            ))}
          </View>
          <PressableScale style={styles.close} onPress={() => overlayStack.closeAll()} accessibilityRole="button" accessibilityLabel={`Close ${title}`} hitSlop={8}>
            <AppText style={styles.closeText}>×</AppText>
          </PressableScale>
        </View>
        {page.header ? (
          <Animated.View style={[styles.head, state.direction !== 'none' && !reduceMotion ? { opacity: slide } : null]} testID="story-header">
            <AppText style={styles.eyebrow}>{page.header.eyebrow}</AppText>
            <AppText style={styles.title} accessibilityRole="header" testID="story-title">{page.header.title}</AppText>
            {page.header.subtitle ? <AppText style={styles.subtitle}>{page.header.subtitle}</AppText> : null}
          </Animated.View>
        ) : (
          <AppText style={styles.kicker}>{page.label}</AppText>
        )}
        <View style={styles.stage} {...pan.panHandlers} onLayout={(e) => (widthRef.current = e.nativeEvent.layout.width)} testID="story-stage">
          {/* Tap zones sit under the page: taps on empty space reach them, taps on controls reach the controls. */}
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityLabel="Tap to move between pages"
            onPress={(e) => {
              const zone = storyTapAction(e.nativeEvent.locationX, widthRef.current);
              if (zone === 'prev') dispatch({ type: 'prev' });
              else if (!storyIsLast(stateRef.current)) dispatch({ type: 'next' });
            }}
          />
          <Animated.View style={[styles.page, { opacity: reduceMotion ? 1 : slide, transform: reduceMotion ? [] : [{ translateX }, { scale: slide.interpolate({ inputRange: [0, 1], outputRange: [0.985, 1] }) }] }]} pointerEvents="box-none" key={page.key} testID={`story-page-${page.key}`}>
            {page.content}
          </Animated.View>
        </View>
        {page.footer ? <View style={styles.foot}>{page.footer}</View> : null}
      </Reanimated.View>
      </GestureDetector>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    top: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.xs },
    progress: { flex: 1, flexDirection: 'row', gap: 4 },
    segHit: { flex: 1, paddingVertical: 8 },
    seg: { height: 4, borderRadius: 2, backgroundColor: colors.border, overflow: 'hidden' },
    segFill: { flex: 1, backgroundColor: colors.accent },
    close: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border, backgroundColor: colors.backgroundElevated ?? 'transparent' },
    closeText: { fontSize: 22, lineHeight: 24, color: colors.textSecondary },
    head: { paddingHorizontal: spacing.lg, gap: 4 },
    eyebrow: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    title: { fontSize: 30, lineHeight: 33, fontWeight: '900', color: colors.textPrimary },
    subtitle: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
    kicker: { paddingHorizontal: spacing.lg, fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    stage: { flex: 1, minHeight: 0 },
    page: { flex: 1, justifyContent: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
    foot: { gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  });
}
