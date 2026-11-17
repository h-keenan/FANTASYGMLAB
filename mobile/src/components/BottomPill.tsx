import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';

import AppText from './AppText';
import PressableScale from './PressableScale';
import TabIcon from './TabIcon';
import { useThemeMode } from '../context/ThemeModeContext';
import { LinearGradient } from 'expo-linear-gradient';
import ToneBadge from './ToneBadge';
import { normalizePillContext, pillActiveIndex, tabShowsPro, pillPrimaryCompact, pillScrollTarget, pillTabText, type PillContext } from '../lib/bottomNav';
import { BAR_METRICS } from '../lib/bottomBarMetrics';
import { EASE, MOTION_MS } from '../lib/motion';
import { radii, type ThemeColors } from '../theme';
import { usePresence } from '../lib/usePresence';
import { haptic } from '../lib/haptic';

/**
 * The app's floating glass pill (twin of web-next components/ui/PillMorph.tsx, approved option B + the V2 smart pill).
 * ONE persistent orb (`orb`) leads the row: it is the only navigation control (it opens the game's page menu; there is no
 * "..." or fold button). Next to it ONE cell holds either the screen's action row (`children`: [Sim to | page action] +
 * Advance) or, when the screen registers a tabbed `segment` (the draft room), the page tabs + one primary chip. What shows
 * when is decided by `simPillPlan` (lib/bottomNav.ts, rules table in docs/ui-patterns.md). The two layers cross-fade and
 * slide on the UI thread (240ms; a crossfade only under OS Reduce Motion), and the segment stays mounted for its exit
 * (lib/presence.ts). Stays an in-flow block in the screen's bottom stack (never absolutely positioned to the screen), so
 * content padding rules are unchanged.
 */
export default function BottomPill({ children, segment: rawContext, orb, style, testID, bare, contextOnly, showPro = false }: { children: React.ReactNode; segment?: PillContext | null; /** The persistent orb. */ orb?: React.ReactNode; style?: StyleProp<ViewStyle>; testID?: string; /** Already inside a glass pill (the Sim bars): draw no chrome of its own. */ bare?: boolean; /** No action row (the draft room has no action bar): the page segment alone. */ contextOnly?: boolean; /** The person is known not to be on Pro (useShowProTags): paid segment tabs wear the Pro marker. */ showPro?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const live = normalizePillContext(rawContext);
  // The page segment stays mounted for its exit when the page's context goes away (it fades out as the default row fades
  // in, t -> 1) and is then removed (lib/presence.ts); with Reduce Motion it simply goes.
  const presence = usePresence(Boolean(live), { exitMs: MOTION_MS.base });
  const [keptRaw, setKeptRaw] = useState<PillContext | null>(rawContext ?? null);
  if (rawContext && rawContext !== keptRaw) setKeptRaw(rawContext);
  const context = live ?? (presence.mounted ? normalizePillContext(keptRaw) : null);
  const reduced = useReducedMotion();
  const t = useSharedValue(0); // 0 = context segment, 1 = default row
  const hasContext = Boolean(live);
  const folded = hasContext || Boolean(contextOnly);
  useEffect(() => {
    t.value = withTiming(folded ? 0 : 1, { duration: reduced ? MOTION_MS.fast : MOTION_MS.base, easing: Easing.bezier(...EASE.out) });
  }, [folded, reduced, t]);
  // Page-tab segment: a horizontal strip that never clips a label. Tabs share the width equally when they fit, scroll with an
  // edge fade when they do not, and the lit tab is scrolled into view. The primary chip collapses to a 40px icon button.
  const [segW, setSegW] = useState(0);
  const [layerW, setLayerW] = useState(0);
  const [content, setContent] = useState({ w: 0, x: 0 });
  const scrollRef = useRef<ScrollView>(null);
  const tabX = useRef<Record<string, { x: number; w: number }>>({});
  const activeKey = context?.activeKey ?? '';
  const scrollToActive = (animated: boolean) => {
    const r = tabX.current[activeKey];
    if (!r || !segW) return;
    scrollRef.current?.scrollTo({ x: pillScrollTarget(r.x, r.w, segW, content.x, content.w), animated });
  };
  useEffect(() => scrollToActive(true), [activeKey, segW, content.w]); // eslint-disable-line react-hooks/exhaustive-deps
  const shift = reduced ? 0 : 14;
  const contextStyle = useAnimatedStyle(() => ({ opacity: 1 - t.value, transform: [{ translateX: -shift * t.value }] }));
  const defaultStyle = useAnimatedStyle(() => ({ opacity: t.value, transform: [{ translateX: shift * (1 - t.value) }] }));

  // Width the tabs and a TEXT chip would share: the cell minus the row gaps (the orb sits outside the cell).
  const compactChip = context ? pillPrimaryCompact(context, layerW - 8) : false;
  return (
    <View style={[bare ? styles.bare : styles.pill, styles.line, style]} testID={testID}>
      {orb}
      <View style={styles.cells}>
      {context ? (
        <Animated.View onLayout={(e) => setLayerW(Math.round(e.nativeEvent.layout.width))} style={[styles.layer, contextStyle, !folded && styles.layerOff]} pointerEvents={folded ? 'auto' : 'none'} accessibilityElementsHidden={!folded} importantForAccessibility={folded ? 'auto' : 'no-hide-descendants'}>
          <View accessibilityRole="tablist" accessibilityLabel={context.label} style={styles.tabs} onLayout={(e) => setSegW(Math.round(e.nativeEvent.layout.width))} testID="pill-tabs">
            <ScrollView
              ref={scrollRef}
              horizontal
              showsHorizontalScrollIndicator={false}
              bounces={false}
              scrollEventThrottle={32}
              onScroll={(e) => setContent((c) => (Math.abs(c.x - e.nativeEvent.contentOffset.x) > 1 ? { ...c, x: Math.round(e.nativeEvent.contentOffset.x) } : c))}
              onContentSizeChange={(w) => setContent((c) => (c.w === w ? c : { ...c, w }))}
              contentContainerStyle={styles.tabsContent}
            >
              {context.tabs.map((tab, i) => {
                const on = i === pillActiveIndex(context);
                return (
                  <PressableScale
                    key={tab.key}
                    accessibilityRole="tab"
                    accessibilityLabel={tabShowsPro(tab, showPro) ? `${tab.label}, Pro feature` : tab.label}
                    accessibilityState={{ selected: on }}
                    onPress={() => {
                      if (!on) haptic('select');
                      context.onSelect(tab.key);
                    }}
                    onLongPress={tab.shortcut ? () => { haptic('select'); tab.shortcut?.onPress(); } : undefined}
                    accessibilityHint={tab.shortcut ? `Long press for ${tab.shortcut.label}` : undefined}
                    onLayout={(e) => { tabX.current[tab.key] = { x: e.nativeEvent.layout.x, w: e.nativeEvent.layout.width }; }}
                    style={[styles.tab, segW > 0 && { minWidth: Math.floor((segW - Math.max(0, context.tabs.length - 1)) / context.tabs.length) }, on && styles.tabOn]}
                  >
                    <AppText style={[styles.tabText, on && styles.tabTextOn]} numberOfLines={1} ellipsizeMode="tail" maxFontSizeMultiplier={1.25}>
                      {pillTabText(tab)}
                    </AppText>
                    {tabShowsPro(tab, showPro) ? <ToneBadge label="Pro" color={colors.premium} size="xs" style={styles.tabPro} /> : null}
                  </PressableScale>
                );
              })}
            </ScrollView>
            {content.w > segW + 1 && content.x + segW < content.w - 1 ? <LinearGradient pointerEvents="none" colors={['transparent', colors.glass]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.fadeEnd} /> : null}
            {content.w > segW + 1 && content.x > 1 ? <LinearGradient pointerEvents="none" colors={[colors.glass, 'transparent']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.fadeStart} /> : null}
          </View>
          {context.primary ? (
            compactChip ? (
              <PressableScale accessibilityRole="button" accessibilityLabel={context.primary.label} disabled={context.primary.disabled || context.primary.busy} onPress={context.primary.onPress} style={[styles.primary, styles.primaryIcon, (context.primary.disabled || context.primary.busy) && { opacity: 0.5 }]} testID="pill-primary">
                <TabIcon name={context.primary.glyph!} color={colors.onAccent} size={18} />
              </PressableScale>
            ) : (
              <PressableScale accessibilityRole="button" accessibilityLabel={context.primary.label} disabled={context.primary.disabled || context.primary.busy} onPress={context.primary.onPress} style={[styles.primary, (context.primary.disabled || context.primary.busy) && { opacity: 0.5 }]} testID="pill-primary">
                <AppText style={styles.primaryText} numberOfLines={1} ellipsizeMode="tail" maxFontSizeMultiplier={1.25}>
                  {context.primary.label}
                </AppText>
              </PressableScale>
            )
          ) : null}
        </Animated.View>
      ) : null}
      {contextOnly ? null : <Animated.View style={[styles.layer, context ? defaultStyle : null, hasContext && styles.layerOff]} pointerEvents={hasContext ? 'none' : 'auto'} accessibilityElementsHidden={hasContext} importantForAccessibility={hasContext ? 'no-hide-descendants' : 'auto'}>
        <View style={styles.fill}>{children}</View>
      </Animated.View>}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  const target = BAR_METRICS.buttonMinHeight;
  return StyleSheet.create({
    // Frosted capsule: the app has no live blur, so the fill is the solid elevated surface (web's --pill-glass-bg is 90%+ opaque);
    // a translucent fill let list text read through the labels.
    pill: {
      borderRadius: 28,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.backgroundElevated,
      paddingHorizontal: BAR_METRICS.pillPadding,
      paddingVertical: BAR_METRICS.pillPadding,
      shadowColor: '#000',
      shadowOpacity: 0.4,
      shadowRadius: 12,
      shadowOffset: { width: 0, height: 6 },
      elevation: 6,
    },
    fill: { flex: 1, minWidth: 0 },
    line: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    cells: { flex: 1, minWidth: 0 },
    bare: { minHeight: target },
    layer: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: target },
    layerOff: { position: 'absolute', left: 0, right: 0, top: 0 },
    tabs: { flex: 1, minWidth: 0, overflow: 'hidden' },
    tabsContent: { flexGrow: 1, alignItems: 'center', gap: 1 },
    fadeEnd: { position: 'absolute', right: 0, top: 0, bottom: 0, width: 18 },
    fadeStart: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 18 },
    tab: { minHeight: target, paddingHorizontal: 5, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderRadius: radii.pill, flexShrink: 0, flexGrow: 1 },
    tabPro: { marginLeft: 4 },
    tabOn: { backgroundColor: colors.glassInset },
    tabText: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    tabTextOn: { color: colors.textPrimary },
    primary: { minHeight: target, paddingHorizontal: 14, justifyContent: 'center', borderRadius: radii.pill, backgroundColor: colors.accentStrong },
    primaryIcon: { width: 44, height: 44, minHeight: 44, paddingHorizontal: 0, alignItems: 'center' },
    primaryText: { fontSize: 12, fontWeight: '800', color: colors.onAccent },
  });
}
