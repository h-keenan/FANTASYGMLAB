import React, { useState } from 'react';
import type { TextProps } from 'react-native';
import AppText from './AppText';

/** "Rhamondre Stevenson" -> "R. Stevenson" — used only once a name is
 * actually about to be clipped (see below), never as the default display. */
function abbreviate(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length < 2) return name;
  return `${parts[0][0]}. ${parts.slice(1).join(' ')}`;
}

/**
 * A single-line player name that degrades to "F. Lastname" instead of
 * trailing off mid-word ("Rhamondre S...") when the container is too
 * narrow for the full name — coridian_'s call after seeing full names clip
 * in the tight trade-exchange chip layout. Detected via onTextLayout
 * (RN reports the untruncated line count even under numberOfLines), not a
 * fixed character-length guess, so it only kicks in where the name
 * genuinely doesn't fit rather than shortening names that already fit.
 */
export default function PlayerNameText({
  name,
  ...rest
}: { name: string } & Omit<TextProps, 'children' | 'numberOfLines' | 'onTextLayout'>) {
  const [clipped, setClipped] = useState(false);
  return (
    <AppText
      {...rest}
      numberOfLines={1}
      onTextLayout={(event) => {
        if (!clipped && event.nativeEvent.lines.length > 1) setClipped(true);
      }}
    >
      {clipped ? abbreviate(name) : name}
    </AppText>
  );
}
