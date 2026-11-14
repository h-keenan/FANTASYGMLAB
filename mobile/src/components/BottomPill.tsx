import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';

import AppText from './AppText';
import PressableScale from './PressableScale';
import TabIcon from './TabIcon';
import { useThemeMode } from '../context/ThemeModeContext';
import { normalizePillContext, pillActiveIndex, PILL_MENU_LABEL, type PillContext } from '../lib/bottomNav';
import { BAR_METRICS } from '../lib/bottomBarMetrics';
import { EASE, MOTION_MS } from '../lib/motion';
import { radii, type ThemeColors } from '../theme';

/**
 * The app's floating glass pill (twin of web-next components/ui/BottomTabBar.tsx, approved option B + the V2 smart pill).
 * The app has no tab bar (GM orb + More), so the pill hosts the screen's bottom action row (`children`: Sim to | orb | Advance)
 * and, when a page registers a `context` (useBottomPillContext), morphs between that row and the page segment (page tabs +
 * one primary chip). The menu button (accessibilityState.expanded) flips between the two layers: 240ms opacity + slide on
 * the UI thread; under OS Reduce Motion it is a crossfade only. Stays an in-flow block in the screen's bottom stack
 * (never absolutely positioned to the screen), so useOrbClearance / content padding rules are unchanged.
 */
export default function BottomPill({ children, context: rawContext, style, testID, bare, contextOnly }: { children: React.ReactNode; context?: PillContext | null; style?: StyleProp<ViewStyle>; testID?: string; /** Already inside a glass pill (the Sim bars): draw no chrome of its own. */ bare?: boolean; /** No row to fold back to (the draft room has no action bar): show the page segment alone, no menu. */ contextOnly?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const context = normalizePillContext(rawContext);
  const reduced = useReducedMotion();
  const [open, setOpen] = useState(false); // true: the default row is showing although a context exists
  const t = useSharedValue(0); // 0 = context segment, 1 = default row
  const hasContext = Boolean(context);
  const contextId = context?.id ?? null;
  const folded = hasContext && (!open || Boolean(contextOnly));
  useEffect(() => setOpen(false), [contextId]);
  useEffect(() => {
    t.value = withTiming(folded ? 0 : 1, { duration: reduced ? MOTION_MS.fast : MOTION_MS.base, easing: Easing.bezier(...EASE.out) });
  }, [folded, reduced, t]);
  const shift = reduced ? 0 : 14;
  const contextStyle = useAnimatedStyle(() => ({ opacity: 1 - t.value, transform: [{ translateX: -shift * t.value }] }));
  const defaultStyle = useAnimatedStyle(() => ({ opacity: t.value, transform: [{ translateX: shift * (1 - t.value) }] }));

  return (
    <View style={[bare ? styles.bare : styles.pill, style]} testID={testID}>
      {context ? (
        <Animated.View style={[styles.layer, contextStyle, !folded && styles.layerOff]} pointerEvents={folded ? 'auto' : 'none'} accessibilityElementsHidden={!folded} importantForAccessibility={folded ? 'auto' : 'no-hide-descendants'}>
          {contextOnly ? null : <PressableScale accessibilityRole="button" accessibilityLabel={PILL_MENU_LABEL} accessibilityState={{ expanded: open }} onPress={() => setOpen(true)} style={styles.iconBtn} testID="pill-menu">
            <TabIcon name="more" color={colors.textSecondary} size={22} />
          </PressableScale>}
          <View style={styles.divider} />
          <View accessibilityRole="tablist" accessibilityLabel={context.label} style={styles.tabs}>
            {context.tabs.map((tab, i) => {
              const on = i === pillActiveIndex(context);
              return (
                <PressableScale key={tab.key} accessibilityRole="tab" accessibilityState={{ selected: on }} onPress={() => context.onSelect(tab.key)} style={[styles.tab, on && styles.tabOn]}>
                  <AppText style={[styles.tabText, on && styles.tabTextOn]} numberOfLines={1}>
                    {tab.label}
                  </AppText>
                </PressableScale>
              );
            })}
          </View>
          {context.primary ? (
            <PressableScale accessibilityRole="button" accessibilityLabel={context.primary.label} disabled={context.primary.disabled || context.primary.busy} onPress={context.primary.onPress} style={[styles.primary, (context.primary.disabled || context.primary.busy) && { opacity: 0.5 }]} testID="pill-primary">
              <AppText style={styles.primaryText} numberOfLines={1}>
                {context.primary.label}
              </AppText>
            </PressableScale>
          ) : null}
        </Animated.View>
      ) : null}
      {contextOnly ? null : <Animated.View style={[styles.layer, hasContext ? defaultStyle : null, hasContext && folded && styles.layerOff]} pointerEvents={hasContext && folded ? 'none' : 'auto'} accessibilityElementsHidden={hasContext && folded} importantForAccessibility={hasContext && folded ? 'no-hide-descendants' : 'auto'}>
        {hasContext ? (
          <PressableScale accessibilityRole="button" accessibilityLabel="Back to page actions" accessibilityState={{ expanded: true }} onPress={() => setOpen(false)} style={styles.iconBtn} testID="pill-menu-close">
            <TabIcon name="more" color={colors.accent} size={22} />
          </PressableScale>
        ) : null}
        <View style={styles.fill}>{children}</View>
      </Animated.View>}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  const target = BAR_METRICS.buttonMinHeight;
  return StyleSheet.create({
    // Frosted capsule (no live blur, same as the app's glass cards): translucent fill, lit rim.
    pill: {
      borderRadius: 28,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
      paddingHorizontal: BAR_METRICS.pillPadding,
      paddingVertical: BAR_METRICS.pillPadding,
      shadowColor: '#000',
      shadowOpacity: 0.4,
      shadowRadius: 12,
      shadowOffset: { width: 0, height: 6 },
      elevation: 6,
    },
    fill: { flex: 1, minWidth: 0 },
    bare: { minHeight: target },
    layer: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: target },
    layerOff: { position: 'absolute', left: 0, right: 0, top: 0 },
    iconBtn: { width: target, height: target, alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill },
    divider: { width: 1, height: 24, backgroundColor: colors.glassBorder },
    tabs: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: 2 },
    tab: { minHeight: target, paddingHorizontal: 8, justifyContent: 'center', borderRadius: radii.pill, flexShrink: 1 },
    tabOn: { backgroundColor: colors.glassInset },
    tabText: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    tabTextOn: { color: colors.textPrimary },
    primary: { minHeight: target, paddingHorizontal: 14, justifyContent: 'center', borderRadius: radii.pill, backgroundColor: colors.accentStrong },
    primaryText: { fontSize: 12, fontWeight: '800', color: colors.onAccent },
  });
}
