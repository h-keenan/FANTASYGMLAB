import React, { useState } from 'react';
import { StyleSheet, View, type TextProps, type TextStyle } from 'react-native';
import AppText from './AppText';
import { PLAYER_NAME_LAST_STAGE, playerNameStage } from '../lib/playerNameFit';

/**
 * The one way the app renders a player name. Owner rule (said five times): when the name does not fit it is the first
 * initial plus the WHOLE surname ("S. Barkley"), never an ellipsis, site-wide. The ladder is `lib/playerNameFit.ts`
 * (shared with web): full name -> "S. Barkley" -> a font step smaller -> two steps smaller -> wrapped onto two lines.
 * No `numberOfLines`/ellipsizeMode on a name anywhere (lib source scan: playerNameTruncation test on web).
 * Twin of web-next/src/components/PlayerName.tsx.
 *
 * Measurement: the visible Text reports the width it was given via onLayout. A hidden, absolutely positioned,
 * uncapped twin of the CURRENT stage is laid out at exactly that width; if it wraps, the stage does not fit and the next
 * one is tried (state, so it re-measures). The width a stage failed at is remembered: when the box grows past it the
 * ladder restarts from the full name. Renders the full name first (no first-frame shift); the last stage may wrap
 * instead of cutting. The full name is the accessibility label.
 */
export default function PlayerName({
  name,
  style,
  // Deprecated: fit is decided by measuring, not a length guess.
  threshold: _threshold,
  ...rest
}: {
  name: string | null | undefined;
  threshold?: number;
} & Omit<TextProps, 'children' | 'numberOfLines' | 'onTextLayout' | 'onLayout'>) {
  const full = (name ?? '').replace(/\s+/g, ' ').trim();
  const [width, setWidth] = useState(0);
  // Tied to the name it was measured for so recycled rows restart from the full name.
  const [fit, setFit] = useState<{ name: string; index: number; failedAt: number }>({ name: full, index: 0, failedAt: 0 });
  const live = fit.name === full ? fit : { name: full, index: 0, failedAt: 0 };
  const stage = playerNameStage(full, live.index);

  const flat = (StyleSheet.flatten(style) ?? {}) as TextStyle;
  const baseSize = typeof flat.fontSize === 'number' ? flat.fontSize : 14;
  const scaled = stage.scale === 1 ? undefined : { fontSize: Math.round(baseSize * stage.scale * 10) / 10, lineHeight: flat.lineHeight ? Math.round(flat.lineHeight * stage.scale) : undefined };
  const fontOnly: TextStyle = {
    fontSize: scaled?.fontSize ?? flat.fontSize,
    fontWeight: flat.fontWeight,
    fontFamily: flat.fontFamily,
    fontStyle: flat.fontStyle,
    letterSpacing: flat.letterSpacing,
    lineHeight: scaled?.lineHeight ?? flat.lineHeight,
  };

  return (
    <>
      <AppText
        {...rest}
        style={[style, scaled]}
        // Never an ellipsis: earlier stages clip for the one frame before the next stage is measured; the last wraps.
        numberOfLines={stage.wrap ? 2 : 1}
        ellipsizeMode="clip"
        accessibilityLabel={full}
        onLayout={(event) => {
          const next = Math.round(event.nativeEvent.layout.width);
          setWidth((prev) => (prev !== next ? next : prev));
          // Room appeared since a stage failed: start again from the full name.
          if (live.index > 0 && live.failedAt > 0 && next > live.failedAt + 1) setFit({ name: full, index: 0, failedAt: 0 });
        }}
      >
        {stage.text}
      </AppText>
      {!stage.wrap && width > 0 && full ? (
        <View pointerEvents="none" style={styles.measureHost} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
          <AppText
            style={[fontOnly, { width: width + 2 }]}
            onTextLayout={(event) => {
              if (event.nativeEvent.lines.length > 1) {
                setFit({ name: full, index: Math.min(PLAYER_NAME_LAST_STAGE, live.index + 1), failedAt: Math.max(live.failedAt, width) });
              }
            }}
          >
            {stage.text}
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
