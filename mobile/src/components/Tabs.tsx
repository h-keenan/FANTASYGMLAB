import React, { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, View, type LayoutChangeEvent } from 'react-native';
import { useReducedMotion } from 'react-native-reanimated';

import SegmentedTabBar from './SegmentedTabBar';
import { nextPanelMinHeight } from '../lib/sheetTabs';
import { createMemoryTabStore, readSavedTab, resolveTab, saveTab, tabDirection } from '../lib/sessionTab';
import type { TabIconName } from '../lib/tabIcons';
import { spacing } from '../theme';

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
  const bar = <SegmentedTabBar<string> slim scrollable options={options} active={current} onChange={select} />;
  const panel = (
    <Animated.View
      accessibilityRole="none"
      onLayout={(e: LayoutChangeEvent) => setMinHeight((prev) => nextPanelMinHeight(prev, e.nativeEvent.layout.height))}
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
