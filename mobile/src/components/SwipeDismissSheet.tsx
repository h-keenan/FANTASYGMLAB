import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef } from 'react';
import { Modal, StyleSheet, View, type ModalProps, type ScrollViewProps, type StyleProp, type ViewStyle } from 'react-native';
import { Gesture, GestureDetector, GestureHandlerRootView, type NativeGesture } from 'react-native-gesture-handler';
import Animated, {
  runOnJS,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
  type SharedValue,
} from 'react-native-reanimated';

import { useThemeMode } from '../context/ThemeModeContext';
import { classifySheetGesture, sheetDragOffset, shouldDismissSheet } from '../lib/sheetGesture';
import { radii, spacing } from '../theme';

/**
 * Swipe-down-to-dismiss for every mobile pop-up (owner, 2026-10-21: "I
 * would still like a gesture to swipe down out of the PQV, or any other
 * pop-up windows"). One gesture, built on the react-native-gesture-handler
 * and Reanimated the app already ships; the thresholds live in
 * lib/sheetGesture.ts and match web-next's exactly.
 *
 * Usage:
 *   <SheetModal visible onRequestClose={close} ...>       // instead of <Modal>
 *     <Pressable style={backdrop} onPress={close}>
 *       <SwipeDismissCard onDismiss={close} style={card}>  // instead of <View>
 *         ...<SheetScrollView>...</SheetScrollView>       // instead of <ScrollView>
 *
 * Rules:
 * - A drag can start anywhere on the card, but only when its SheetScrollView
 *   (if any) is scrolled to the top. Scrolling back up inside a long card
 *   never closes it. A touch that starts on the grab bar always drags.
 * - Mostly-horizontal and upward gestures are left alone (8px slop).
 * - The card follows the finger, with rubber-band resistance past the
 *   dismiss distance and when pulled upward.
 * - On release it closes when pulled past a quarter of its height (80 to
 *   160px) or flicked down fast; otherwise it springs back.
 * - Close buttons and Modal onRequestClose (Android back) are untouched.
 */

/** Height of the grab-bar zone at the top of a card: a touch that starts
 * here always drags, even when the content below is scrolled. */
const HANDLE_ZONE = 28;
const CLOSE_MS = 200;
const SNAP_BACK_SPRING = { damping: 18, stiffness: 220, mass: 0.8 };

interface SheetScrollContextValue {
  scrollY: SharedValue<number>;
  nativeScroll: NativeGesture;
}

const SheetScrollContext = createContext<SheetScrollContextValue | null>(null);

/**
 * The pan gesture behind every swipe-to-dismiss surface. Exposed (not only
 * used by SwipeDismissCard) so a sheet that already owns its own
 * translateY animation can attach the same gesture to it.
 *
 * `translateY` is the surface's vertical offset. When the release crosses
 * the threshold, `onDismiss` runs; with `slideOut` the hook first animates
 * the surface off-screen, otherwise the caller's own close animation
 * continues from wherever the finger left it.
 */
export function useSheetDismissGesture({
  translateY,
  sheetHeight,
  onDismiss,
  enabled = true,
  slideOut = true,
  handleOnly = false,
}: {
  translateY: SharedValue<number>;
  sheetHeight: SharedValue<number>;
  onDismiss: () => void;
  enabled?: boolean;
  slideOut?: boolean;
  /** Only a touch that starts on the grab bar may drag — for cards whose
   * scrolling content can't be a SheetScrollView (e.g. a SectionList), so
   * scrolling it can never be mistaken for a dismiss. */
  handleOnly?: boolean;
}): { gesture: ReturnType<typeof Gesture.Pan>; scrollContext: SheetScrollContextValue } {
  const scrollY = useSharedValue(0);
  const startX = useSharedValue(0);
  const startY = useSharedValue(0);
  const startedOnHandle = useSharedValue(false);

  // Stable JS callback for runOnJS, always calling the latest onDismiss.
  const onDismissRef = useRef(onDismiss);
  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);
  const dismiss = useCallback(() => onDismissRef.current(), []);

  const nativeScroll = useMemo(() => Gesture.Native(), []);

  const gesture = useMemo(
    () =>
      Gesture.Pan()
        .enabled(enabled)
        .manualActivation(true)
        .simultaneousWithExternalGesture(nativeScroll)
        .onTouchesDown((event) => {
          const touch = event.allTouches[0];
          if (!touch) return;
          startX.value = touch.absoluteX;
          startY.value = touch.absoluteY;
          startedOnHandle.value = touch.y <= HANDLE_ZONE;
        })
        .onTouchesMove((event, manager) => {
          const touch = event.allTouches[0];
          if (!touch || event.numberOfTouches > 1) {
            manager.fail();
            return;
          }
          const decision = classifySheetGesture({
            dx: touch.absoluteX - startX.value,
            dy: touch.absoluteY - startY.value,
            canStartDrag: startedOnHandle.value || (!handleOnly && scrollY.value <= 0),
          });
          if (decision === 'drag') manager.activate();
          else if (decision === 'ignore') manager.fail();
        })
        .onUpdate((event) => {
          translateY.value = sheetDragOffset(event.translationY, sheetHeight.value);
        })
        .onEnd((event) => {
          const close = shouldDismissSheet({
            offset: translateY.value,
            velocity: event.velocityY / 1000,
            sheetHeight: sheetHeight.value,
          });
          if (!close) {
            translateY.value = withSpring(0, SNAP_BACK_SPRING);
            return;
          }
          if (!slideOut) {
            runOnJS(dismiss)();
            return;
          }
          translateY.value = withTiming(sheetHeight.value + 48, { duration: CLOSE_MS }, (finished) => {
            if (finished) runOnJS(dismiss)();
          });
        }),
    [enabled, slideOut, handleOnly, nativeScroll, dismiss, scrollY, startX, startY, startedOnHandle, translateY, sheetHeight],
  );

  const scrollContext = useMemo(() => ({ scrollY, nativeScroll }), [scrollY, nativeScroll]);
  return { gesture, scrollContext };
}

/**
 * Drop-in for React Native's <Modal> on any pop-up that uses
 * SwipeDismissCard. Modals render outside the app's root
 * GestureHandlerRootView (so gestures inside them do nothing on Android
 * without their own root); this adds one that fills the modal and changes
 * nothing else.
 */
export function SheetModal({ children, ...modalProps }: ModalProps & { children: React.ReactNode }) {
  return (
    <Modal {...modalProps}>
      <GestureHandlerRootView style={styles.root}>{children}</GestureHandlerRootView>
    </Modal>
  );
}

/**
 * The pop-up's card: a drop-in for the card <View> with the grab bar on
 * top and the swipe-down gesture attached. `style` is the card's existing
 * style; nothing about its look changes besides the grab bar.
 */
export function SwipeDismissCard({
  onDismiss,
  enabled = true,
  showHandle = true,
  handleOnly = false,
  style,
  testID,
  children,
}: {
  onDismiss: () => void;
  enabled?: boolean;
  showHandle?: boolean;
  handleOnly?: boolean;
  testID?: string;
  style?: StyleProp<ViewStyle>;
  children: React.ReactNode;
}) {
  const translateY = useSharedValue(0);
  const sheetHeight = useSharedValue(0);
  const { gesture, scrollContext } = useSheetDismissGesture({ translateY, sheetHeight, onDismiss, enabled, handleOnly });
  const animatedStyle = useAnimatedStyle(() => ({ transform: [{ translateY: translateY.value }] }));

  return (
    <SheetScrollContext.Provider value={scrollContext}>
      <GestureDetector gesture={gesture}>
        <Animated.View
          testID={testID}
          style={[style, animatedStyle]}
          // Claims taps on the card's own blank space so they never reach a
          // tap-to-close backdrop behind it (what the old inner
          // <Pressable onPress={e => e.stopPropagation()}> did). Buttons
          // inside still win: the deepest touchable responds first.
          onStartShouldSetResponder={() => true}
          onLayout={(event) => {
            sheetHeight.value = event.nativeEvent.layout.height;
          }}
        >
          {showHandle ? <SheetHandle /> : null}
          {children}
        </Animated.View>
      </GestureDetector>
    </SheetScrollContext.Provider>
  );
}

/** Provides a sheet's scroll context to content rendered outside
 * SwipeDismissCard, for sheets that use useSheetDismissGesture directly. */
export const SheetScrollProvider = SheetScrollContext.Provider;

/**
 * ScrollView for content inside a SwipeDismissCard. It reports its offset
 * so a downward drag only closes the card at the top, and runs alongside
 * the card's gesture. No overscroll bounce at the top, so a pull-down there
 * moves the card instead of the content. Outside a card it is a plain
 * Animated ScrollView.
 */
export function SheetScrollView(props: ScrollViewProps & { children?: React.ReactNode }) {
  const context = useContext(SheetScrollContext);
  const scrollY = context?.scrollY;
  const onScroll = useAnimatedScrollHandler({
    onScroll: (event) => {
      if (scrollY) scrollY.value = event.contentOffset.y;
    },
  });
  const scrollView = (
    <Animated.ScrollView
      {...props}
      onScroll={onScroll}
      scrollEventThrottle={16}
      bounces={false}
      overScrollMode="never"
    />
  );
  if (!context) return scrollView;
  return <GestureDetector gesture={context.nativeScroll}>{scrollView}</GestureDetector>;
}

/** The grab bar: same size and color as the GM orb sheet's handle. */
export function SheetHandle() {
  const { colors } = useThemeMode();
  return (
    <View style={styles.handleRow} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <View style={[styles.handle, { backgroundColor: colors.borderStrong }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  handleRow: { alignItems: 'center', paddingTop: spacing.xs, paddingBottom: spacing.sm },
  handle: { width: 36, height: 4, borderRadius: radii.pill },
});
