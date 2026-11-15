import React, { useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, View, type StyleProp, type ViewStyle } from 'react-native';

import { EASE } from '../lib/motion';
import {
  dropPresenceEntry,
  mergePresenceEntries,
  presenceFrame,
  shouldAnimatePresenceList,
  type PresenceEntry,
  type PresenceVariant,
} from '../lib/presence';
import { usePresence } from '../lib/usePresence';

/**
 * THE appear / disappear primitive (twin of web-next's components/ui/Presence.tsx; docs/ui-patterns.md "Presence").
 * Anything that shows or hides (a toast, a banner, an expander body, a list row, a swapped body) goes through this
 * instead of `cond && <X />`, so nothing pops. It mounts on `show`, animates in, and on hide animates out and only then
 * unmounts, keeping the last children on screen while it leaves. Opacity, transform and (variant 'collapse') a measured
 * height only; 120-300ms (lib/presence.ts); with OS Reduce Motion it simply appears and disappears.
 *
 * Variants: 'fade', 'rise' (+ a short lift: toasts, banners), 'pop' (+ a small scale), 'collapse' (measured height + opacity:
 * expander bodies, list rows). `appear` animates in when already shown on first render.
 */
export function Presence({
  show,
  variant = 'fade',
  appear = false,
  enterMs,
  exitMs,
  onExited,
  style,
  testID,
  children,
}: {
  show: boolean;
  variant?: PresenceVariant;
  appear?: boolean;
  enterMs?: number;
  exitMs?: number;
  onExited?: () => void;
  style?: StyleProp<ViewStyle>;
  testID?: string;
  children?: ReactNode;
}) {
  const state = usePresence(show, { enterMs, exitMs, appear, onExited });
  const { phase } = state;
  // Keep the last shown children so the exit has something to play on after the caller stops rendering them.
  const [kept, setKept] = useState<ReactNode>(children);
  if (show && kept !== children) setKept(children);

  const collapse = variant === 'collapse';
  // `shown` (native driver): opacity and transform. `open` (JS driver): the measured height, collapse only.
  const shown = useRef(new Animated.Value(phase === 'entered' ? 1 : 0)).current;
  const open = useRef(new Animated.Value(phase === 'entered' ? 1 : 0)).current;
  const [measured, setMeasured] = useState<number | null>(null);

  useEffect(() => {
    if (phase !== 'entering' && phase !== 'exiting') {
      const rest = phase === 'entered' ? 1 : 0;
      shown.setValue(rest);
      open.setValue(rest);
      return;
    }
    // A collapse cannot enter before its body has been measured.
    if (phase === 'entering' && collapse && measured === null) return;
    const to = phase === 'entering' ? 1 : 0;
    const ms = phase === 'entering' ? state.enterMs : state.exitMs;
    const curve = phase === 'entering' ? EASE.out : EASE.in;
    const easing = Easing.bezier(curve[0], curve[1], curve[2], curve[3]);
    const run = Animated.parallel([
      Animated.timing(shown, { toValue: to, duration: ms, easing, useNativeDriver: true }),
      Animated.timing(open, { toValue: to, duration: ms, easing, useNativeDriver: false }),
    ]);
    run.start();
    return () => run.stop();
  }, [phase, measured, collapse, shown, open, state.enterMs, state.exitMs]);

  if (!state.mounted) return null;
  const hidden = presenceFrame(variant, false);
  const body = (
    <Animated.View
      style={{
        opacity: shown,
        transform: [
          { translateY: shown.interpolate({ inputRange: [0, 1], outputRange: [hidden.translateY, 0] }) },
          { scale: shown.interpolate({ inputRange: [0, 1], outputRange: [hidden.scale, 1] }) },
        ],
      }}
    >
      {show ? children : kept}
    </Animated.View>
  );
  if (!collapse) {
    return (
      <View style={style} testID={testID} pointerEvents={phase === 'exiting' ? 'none' : 'auto'}>
        {body}
      </View>
    );
  }
  // At rest the body has its natural height; only while animating is it clipped to a height between 0 and the measured one.
  const animating = phase === 'entering' || phase === 'exiting';
  const heightStyle =
    animating && measured !== null
      ? { height: open.interpolate({ inputRange: [0, 1], outputRange: [0, measured] }), overflow: 'hidden' as const }
      : animating
        ? { height: 0, overflow: 'hidden' as const }
        : null;
  return (
    <Animated.View style={[style, heightStyle]} testID={testID} pointerEvents={phase === 'exiting' ? 'none' : 'auto'}>
      <View onLayout={(event) => setMeasured(Math.round(event.nativeEvent.layout.height))}>{body}</View>
    </Animated.View>
  );
}

/** An expander body: `<Collapse open={open}>…</Collapse>` replaces `{open ? <View>…</View> : null}`. Height + opacity, measured. */
export function Collapse({ open, appear = false, style, testID, children }: { open: boolean; appear?: boolean; style?: StyleProp<ViewStyle>; testID?: string; children?: ReactNode }) {
  return (
    <Presence show={open} variant="collapse" appear={appear} style={style} testID={testID}>
      {children}
    </Presence>
  );
}

/**
 * Rows that are added and removed: a row leaving plays its exit in the place it was, then goes; a new row enters. Lists
 * longer than 24 rows do not animate. `render` gets the item and its index among the CURRENT items.
 */
export function PresenceList<T>({
  items,
  getKey,
  render,
  variant = 'collapse',
  appear = false,
  rowStyle,
}: {
  items: readonly T[];
  getKey: (item: T) => string;
  render: (item: T, index: number) => ReactNode;
  variant?: PresenceVariant;
  appear?: boolean;
  rowStyle?: StyleProp<ViewStyle>;
}) {
  const [entries, setEntries] = useState<PresenceEntry<T>[]>(() => items.map((item) => ({ key: getKey(item), item, present: true })));
  // Rows that were there on first render are simply there; a row added later enters.
  const [initialKeys] = useState(() => new Set(items.map(getKey)));
  const animate = shouldAnimatePresenceList(items.length);
  const merged = mergePresenceEntries(entries, items, getKey);
  const same = merged.length === entries.length && merged.every((m, i) => m.key === entries[i].key && m.present === entries[i].present && m.item === entries[i].item);
  if (!same) setEntries(animate ? merged : merged.filter((m) => m.present));
  const visible = animate ? merged : merged.filter((m) => m.present);
  const presentKeys = visible.filter((entry) => entry.present).map((entry) => entry.key);
  return (
    <>
      {visible.map((entry) => {
        return (
          <Presence
            key={entry.key}
            show={entry.present}
            variant={variant}
            appear={appear || !initialKeys.has(entry.key)}
            style={rowStyle}
            onExited={() => setEntries((prev) => dropPresenceEntry(prev, entry.key))}
          >
            {render(entry.item, Math.max(0, presentKeys.indexOf(entry.key)))}
          </Presence>
        );
      })}
    </>
  );
}

/**
 * A body that is replaced when `swapKey` changes (a sheet's tab content, a stepper's page): the old one fades out, then the
 * new one rises in, instead of one frame swapping them. Same key = it just re-renders. Reduce Motion: an instant swap.
 */
export function PresenceSwap({ swapKey, children, style }: { swapKey: string; children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const [shown, setShown] = useState<{ key: string; node: ReactNode }>({ key: swapKey, node: children });
  if (shown.key === swapKey && shown.node !== children) setShown({ key: swapKey, node: children });
  const incoming = shown.key !== swapKey;
  return (
    <Presence
      show={!incoming}
      variant="rise"
      style={style}
      onExited={() => {
        // The old body has left: bring the new one in.
        setShown({ key: swapKey, node: children });
      }}
    >
      {shown.node}
    </Presence>
  );
}

export default Presence;
