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
        // Can't check `lines.length > 1` here — with numberOfLines={1} also
        // set, RN caps the reported lines at 1 no matter what, so that check
        // can never fire (this was the actual bug: names kept clipping to
        // "Rhamondre S..." instead of abbreviating). A truncated line's
        // reported text is always shorter than the real name (RN appends an
        // ellipsis and drops what didn't fit), so compare lengths instead.
        const renderedText = event.nativeEvent.lines[0]?.text ?? '';
        if (!clipped && renderedText.length > 0 && renderedText.length < name.trim().length) {
          setClipped(true);
        }
      }}
    >
      {clipped ? abbreviate(name) : name}
    </AppText>
  );
}
