import React, { useState } from 'react';
import { StyleSheet, View, type TextProps, type TextStyle } from 'react-native';
import AppText from './AppText';
import { shortPlayerName } from '../lib/playerNameDisplay';

/**
 * The one way the app renders a player name in a row or card where it could
 * be truncated. Owner rule: when the full name does not fit it reads
 * "S. Barkley" (first initial + whole surname, suffix kept); only if that
 * STILL does not fit does the surname ellipsize (numberOfLines={1}).
 * Twin of web-next/src/components/PlayerName.tsx.
 *
 * Measurement: the visible Text (numberOfLines 1) reports the width it was
 * given via onLayout. A hidden, absolutely positioned twin of the FULL name
 * is laid out at exactly that width with no line cap; if it wraps onto a
 * second line the full name does not fit and the short form is shown. The
 * twin is out of flow (no layout impact, no gap/space-between side effects),
 * is skipped for names that cannot shrink, and decides on real text layout
 * rather than a character-count guess. Renders the full name first, so there
 * is no first-frame layout shift; the decision only changes on a measured
 * transition, so it cannot loop (the twin always measures the full name).
 *
 * The full name is exposed as the accessibility label.
 */
export default function PlayerName({
  name,
  style,
  // Deprecated: shortening is decided by measured fit, not a length guess.
  threshold: _threshold,
  ...rest
}: {
  name: string | null | undefined;
  threshold?: number;
} & Omit<TextProps, 'children' | 'numberOfLines' | 'onTextLayout' | 'onLayout'>) {
  const full = (name ?? '').trim();
  const short = shortPlayerName(full);
  const canShrink = short !== full;
  const [width, setWidth] = useState(0);
  // Tied to the name it was measured for so recycled rows re-measure.
  const [shortFor, setShortFor] = useState<string | null>(null);
  const useShort = canShrink && shortFor === full;

  const flat = (StyleSheet.flatten(style) ?? {}) as TextStyle;
  const fontOnly: TextStyle = {
    fontSize: flat.fontSize,
    fontWeight: flat.fontWeight,
    fontFamily: flat.fontFamily,
    fontStyle: flat.fontStyle,
    letterSpacing: flat.letterSpacing,
    lineHeight: flat.lineHeight,
  };

  return (
    <>
      <AppText
        {...rest}
        style={style}
        numberOfLines={1}
        accessibilityLabel={full}
        onLayout={(event) => {
          const next = Math.round(event.nativeEvent.layout.width);
          setWidth((prev) => (Math.abs(prev - next) > 0 ? next : prev));
        }}
      >
        {useShort ? short : full}
      </AppText>
      {canShrink && width > 0 ? (
        <View pointerEvents="none" style={styles.measureHost} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
          <AppText
            style={[fontOnly, { width: width + 2 }]}
            onTextLayout={(event) => {
              const wraps = event.nativeEvent.lines.length > 1;
              setShortFor((prev) => (wraps ? (prev === full ? prev : full) : prev === null ? prev : null));
            }}
          >
            {full}
          </AppText>
        </View>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  // Out of flow: never affects the parent's layout.
  measureHost: { position: 'absolute', left: 0, top: 0, opacity: 0 },
});
