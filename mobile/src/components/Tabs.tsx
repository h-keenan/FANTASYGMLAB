import React, { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, View, type LayoutChangeEvent } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { haptic } from '../lib/haptic';
import Reanimated, { runOnJS, useAnimatedStyle, useReducedMotion, useSharedValue, withSpring } from 'react-native-reanimated';

import SegmentedTabBar from './SegmentedTabBar';
import { nextPanelMinHeight } from '../lib/sheetTabs';
import { createMemoryTabStore, readSavedTab, resolveTab, saveTab, tabDirection } from '../lib/sessionTab';
import type { TabIconName } from '../lib/tabIcons';
import { spacing } from '../theme';
import { swipeLock } from './swipeLock';
import { decideSwipe, lockSwipeAxis, swipeMayStart, swipeProgress } from '../lib/swipeTabs';

export interface TabItem {
  key: string;
  label: string;
  glyph?: TabIconName;
  /** Small count pill beside the label. */
  count?: number;
  /** Rendered only while this tab is open (panels are lazy, so a heavy tab costs nothing until it is picked). */
  render: () => ReactNode;
}

// The last tab per surface, for the app session (module scope: survives a sheet closing and reopening).
const sessionTabs = createMemoryTabStore();

/**
 * THE tabs for a surface that has more to say than one screen (player sheet, team sheet): the shared segmented tab
 * strip (in its slim in-sheet look) over lazily rendered panels. Built on the existing control, not beside it. Adds a
 * short slide-in from the side you moved toward (instant under reduced motion) and the last tab remembered for the
 * session under `id`. Twin of web-next's Tabs.
 *
 * `useTabs` hands back the strip (`bar`) and the panel separately so a sheet can make the strip a direct child of its
 * ScrollView and pin it with `stickyHeaderIndices` (the sticky tab bar); `Tabs` is the same two pieces stacked, for
 * surfaces that do not need it. The panel keeps the tallest height it has shown as its minimum, so switching to a
 * short tab never pulls the sheet up (no layout jump).
 */
export function useTabs({ id, tabs, initial, onChange }: { id: string; tabs: readonly TabItem[]; initial?: string; onChange?: (key: string) => void }) {
  const keys = tabs.map((t) => t.key);
  const [active, setActive] = useState(() => resolveTab(readSavedTab(sessionTabs, id), keys, initial));
  const current = keys.includes(active) ? active : resolveTab(null, keys, initial);
  const previous = useRef(current);
  const reduceMotion = useReducedMotion();
  const slide = useRef(new Animated.Value(1)).current;
  const dir = useRef<-1 | 0 | 1>(0);
  const [minHeight, setMinHeight] = useState(0);

  function select(key: string) {
    dir.current = tabDirection(keys, previous.current, key);
    previous.current = key;
    setActive(key);
    saveTab(sessionTabs, id, key);
    onChange?.(key);
  }

  // Slide the new panel in: opacity + translateX only (native driver), skipped for reduced motion and the first paint.
  useEffect(() => {
    if (reduceMotion || dir.current === 0) {
      slide.setValue(1);
      return;
    }
    slide.setValue(0);
    Animated.timing(slide, { toValue: 1, duration: 160, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
  }, [current, reduceMotion, slide]);

  const options = useMemo(() => tabs.map((t) => ({ key: t.key, label: t.label, glyph: t.glyph, count: t.count })), [tabs]);
  const tab = tabs.find((t) => t.key === current);
  const from = dir.current * 14;
  // Swipe left/right to change tabs (an addition: the tab buttons stay). Manual-activation pan so it only takes clearly
  // horizontal drags that did not start in a horizontal scroller (swipeLock), and leaves vertical scroll and the
  // sheet's drag-to-dismiss alone. The panel and the strip's indicator follow the finger on the UI thread, then spring.
  const progress = useSharedValue(0);
  const startX = useSharedValue(0);
  const startY = useSharedValue(0);
  const blocked = useSharedValue(false);
  const width = useSharedValue(1);
  const index = keys.indexOf(current);
  const nav = useSharedValue({ i: index, n: keys.length });
  nav.value = { i: index, n: keys.length };
  const commit = (target: string) => {
    if (target === previous.current) return;
    haptic('select');
    select(target);
  };
  const keysRef = useRef(keys);
  useEffect(() => {
    keysRef.current = keys;
  });
  const pickByIndex = (i: number) => {
    const k = keysRef.current[i];
    if (k) commit(k);
  };
  const swipe = useMemo(
    () =>
      Gesture.Pan()
        .manualActivation(true)
        .onTouchesDown((e) => {
          const t = e.allTouches[0];
          if (!t) return;
          startX.value = t.absoluteX;
          startY.value = t.absoluteY;
          blocked.value = !swipeMayStart({ startX: t.absoluteX, viewportWidth: 1e9, inHorizontalScroller: swipeLock.value, edgeGuard: 0 });
        })
        .onTouchesMove((e, manager) => {
          const t = e.allTouches[0];
          if (!t || e.numberOfTouches > 1 || blocked.value || swipeLock.value) {
            manager.fail();
            return;
          }
          const axis = lockSwipeAxis(t.absoluteX - startX.value, t.absoluteY - startY.value);
          if (axis === 'horizontal') manager.activate();
          else if (axis === 'vertical') manager.fail();
        })
        .onUpdate((e) => {
          if (reduceMotion) return;
          progress.value = swipeProgress(e.translationX, width.value, nav.value.i > 0, nav.value.i < nav.value.n - 1);
        })
        .onEnd((e) => {
          const { i, n } = nav.value;
          const decision = decideSwipe(e.translationX, e.translationY, e.velocityX / 1000, i > 0, i < n - 1);
          if (decision !== 'none') runOnJS(pickByIndex)(decision === 'next' ? i + 1 : i - 1);
          progress.value = reduceMotion ? 0 : withSpring(0, { damping: 18, stiffness: 240, mass: 0.8 });
        })
        .onFinalize(() => {
          swipeLock.value = false;
        }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [reduceMotion],
  );
  const dragStyle = useAnimatedStyle(() => ({
    opacity: 1 - Math.abs(progress.value) * 0.35,
    transform: [{ translateX: progress.value * 56 }],
  }));
  const bar = <SegmentedTabBar<string> slim scrollable options={options} active={current} onChange={select} drag={progress} />;
  const panelInner = (
    <Animated.View
      accessibilityRole="none"
      onLayout={(e: LayoutChangeEvent) => (width.value = e.nativeEvent.layout.width || 1, setMinHeight((prev) => nextPanelMinHeight(prev, e.nativeEvent.layout.height)))}
      style={{
        gap: spacing.lg,
        minHeight: minHeight > 0 ? minHeight : undefined,
        opacity: slide,
        transform: [{ translateX: slide.interpolate({ inputRange: [0, 1], outputRange: [from, 0] }) }],
      }}
    >
      {tab ? tab.render() : null}
    </Animated.View>
  );
  const panel = (
    <GestureDetector gesture={swipe}>
      <Reanimated.View style={dragStyle}>{panelInner}</Reanimated.View>
    </GestureDetector>
  );
  return { bar, panel, active: current };
}

export default function Tabs(props: { id: string; tabs: readonly TabItem[]; initial?: string; onChange?: (key: string) => void }) {
  const { bar, panel } = useTabs(props);
  return (
    <View style={{ gap: spacing.md }}>
      {bar}
      {panel}
    </View>
  );
}
