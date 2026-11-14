import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Easing, ScrollView, StyleSheet, TouchableOpacity, View, type LayoutChangeEvent } from 'react-native';
import { useReducedMotion } from 'react-native-reanimated';

import AppText from './AppText';
import { PulseOnIncrease } from './Motion';
import TabIcon from './TabIcon';
import type { TabIconName } from '../lib/tabIcons';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

export interface SegmentedTabOption<T extends string> {
  key: T;
  label: string;
  /** Glyph from the shared registry (lib/tabIcons.ts), stacked over the label. Same names as web's PillRow. */
  glyph?: TabIconName;
  /** Optional raw glyph slot when the registry has no fitting name. */
  icon?: React.ReactNode;
  /** Small count pill beside the label. */
  count?: number;
}

/**
 * One cohesive segmented control — a single shared track holding all
 * options, with the active option rendered as an illuminated cyan pill and
 * every other option as plain understated text — replacing the old row of
 * individually-bordered pill buttons (which read as a set of disconnected
 * buttons rather than one control). Generic over the tab key type so it can
 * back Player Detail's Stats/Trends/Schedule/Career/Model tabs today and any
 * other screen's tab row later without a second implementation.
 */
export default function SegmentedTabBar<T extends string>({
  options,
  active,
  onChange,
  scrollable = false,
  slim = false,
}: {
  options: Array<SegmentedTabOption<T>>;
  active: T;
  onChange: (key: T) => void;
  /** Many options: segments size to their label and the track scrolls sideways
   * (web's PillRow variant="scroll"). */
  scrollable?: boolean;
  /** The sleek in-sheet look (shared Tabs): no outer box or pill, a hairline under the strip and a sliding underline. */
  slim?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const reduceMotion = useReducedMotion();
  // Sliding glass pill behind the active segment: measured per segment, moved
  // in ~180ms (instant under reduce-motion). Until measured, the active
  // segment paints its own pill so nothing flashes unstyled.
  const [layouts, setLayouts] = useState<Record<string, { x: number; width: number }>>({});
  const slideX = useRef(new Animated.Value(0)).current;
  const slideW = useRef(new Animated.Value(0)).current;
  const placed = useRef(false);
  const target = layouts[active];
  useEffect(() => {
    if (!target) return;
    if (!placed.current || reduceMotion) {
      slideX.setValue(target.x);
      slideW.setValue(target.width);
      placed.current = true;
      return;
    }
    const config = { duration: 180, easing: Easing.out(Easing.cubic), useNativeDriver: false };
    Animated.parallel([Animated.timing(slideX, { toValue: target.x, ...config }), Animated.timing(slideW, { toValue: target.width, ...config })]).start();
  }, [target, reduceMotion, slideX, slideW]);
  const onSegmentLayout = (key: string) => (event: LayoutChangeEvent) => {
    const { x, width } = event.nativeEvent.layout;
    setLayouts((prev) => (prev[key] && prev[key].x === x && prev[key].width === width ? prev : { ...prev, [key]: { x, width } }));
  };
  // Five or more tabs: tighter label + padding so the last one is never clipped at 390px.
  const dense = !scrollable && options.length >= 5;
  const body = (
    <View style={[styles.track, scrollable && styles.trackScroll, slim && styles.trackSlim]} accessibilityRole="tablist">
      {target ? <Animated.View pointerEvents="none" style={[styles.slider, slim && styles.sliderSlim, { left: 0, transform: [{ translateX: slideX }], width: slideW }]} /> : null}
      {options.map((option) => {
        const isActive = option.key === active;
        const iconColor = isActive ? colors.accent : colors.textTertiary;
        return (
          <TouchableOpacity
            key={option.key}
            style={[styles.segment, scrollable && styles.segmentScroll, dense && styles.segmentDense, isActive && !target && (slim ? styles.segmentActiveSlim : styles.segmentActive)]}
            onPress={() => onChange(option.key)}
            onLayout={onSegmentLayout(option.key)}
            activeOpacity={0.75}
            accessibilityRole="tab"
            accessibilityState={{ selected: isActive }}
            accessibilityLabel={option.label}
          >
            {option.glyph ? (
              <View style={styles.icon}>
                <TabIcon name={option.glyph} color={iconColor} />
              </View>
            ) : option.icon ? (
              <View style={styles.icon}>{option.icon}</View>
            ) : null}
            <View style={styles.labelRow}>
              <AppText style={[styles.label, dense && styles.labelDense, isActive && styles.labelActive]} numberOfLines={1}>
                {option.label}
              </AppText>
              {option.count ? (
                <View style={[styles.countPill, Boolean(option.glyph || option.icon) && styles.countPillOverlay]} accessibilityLabel={`${option.count} new`}>
                  <PulseOnIncrease value={option.count}><AppText style={styles.countText}>{option.count}</AppText></PulseOnIncrease>
                </View>
              ) : null}
            </View>
          </TouchableOpacity>
        );
      })}
    </View>
  );
  return scrollable ? (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ flexGrow: 1 }}>
      {body}
    </ScrollView>
  ) : (
    body
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    track: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.background,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.border,
      padding: 3,
      gap: 2,
    },
    segment: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 44,
      borderRadius: radii.pill,
    },
    trackScroll: { alignSelf: 'stretch', flexGrow: 1 },
    trackSlim: { backgroundColor: 'transparent', borderWidth: 0, borderBottomWidth: StyleSheet.hairlineWidth, borderRadius: 0, padding: 0, gap: 0 },
    sliderSlim: { top: undefined, bottom: 0, height: 2, borderRadius: 0, borderWidth: 0, backgroundColor: colors.accent },
    segmentActiveSlim: { borderBottomWidth: 2, borderBottomColor: colors.accent },
    // Share a short row equally (no empty box after the last tab); keep the natural width and scroll when they overflow.
    segmentScroll: { flexGrow: 1, flexShrink: 0, flexBasis: 'auto', paddingHorizontal: 12 },
    segmentDense: { paddingHorizontal: 0 },
    slider: {
      position: 'absolute',
      top: 3,
      bottom: 3,
      borderRadius: radii.pill,
      backgroundColor: colors.accentMuted,
      borderWidth: 1,
      borderColor: colors.accent,
    },
    segmentActive: {
      backgroundColor: colors.accentMuted,
      borderWidth: 1,
      borderColor: colors.accent,
    },
    icon: { marginBottom: 1 },
    labelRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    countPill: { minWidth: 16, height: 16, paddingHorizontal: 4, borderRadius: radii.pill, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent },
    countPillOverlay: { position: 'absolute', top: -4, right: -12 },
    countText: { fontSize: 12, fontWeight: '800', color: colors.onAccent },
    labelDense: { fontSize: 12, letterSpacing: -0.2 },
    label: { fontSize: 13.5, fontWeight: '600', letterSpacing: -0.2, color: colors.textSecondary },
    // accentOnTint, not accent: this label sits directly on `segmentActive`'s
    // accentMuted fill, where light mode's plain accent falls under AA
    // contrast (color-system audit, 2026-09-25 — see theme.ts).
    labelActive: { color: colors.accentOnTint, fontWeight: '700' },
  });
}
