import React, { useMemo, useState } from 'react';
import type { TextProps } from 'react-native';
import AppText from './AppText';
import { abbreviatePlayerName, shouldAbbreviatePlayerName } from '../lib/formatPlayerName';

/**
 * A single-line player name that degrades to "F. Lastname" instead of
 * trailing off mid-word ("Rhamondre S...") when the container is too
 * narrow for the full name — coridian_'s call after seeing full names clip
 * in the tight trade-exchange chip layout.
 *
 * Primary mechanism: a synchronous, deterministic character-length
 * threshold (`shouldAbbreviatePlayerName`), decided on first render with no
 * layout callback round-trip. This replaced an onTextLayout-only detection
 * that turned out to be unreliable in production — screenshots showed
 * several different long names simultaneously still rendering truncated
 * mid-word in the same render, which isn't what a one-frame detection race
 * looks like; RN's reported `lines[0].text` just doesn't reliably reflect
 * the real `numberOfLines`-truncated output across every RN/Hermes version
 * and layout context. See formatPlayerName.ts for how the threshold itself
 * was calibrated.
 *
 * `onTextLayout` is kept as a secondary, best-effort correction for the
 * rare name that lands just under the threshold but still doesn't fit in
 * some caller's narrower-than-calibrated context — never the only
 * mechanism, since that's the demonstrated-unreliable path. `numberOfLines
 * ={1}` stays on as the final backstop regardless: if something genuinely
 * unexpected is still too long despite passing both checks, it clips
 * safely instead of overflowing the row.
 */
export default function PlayerNameText({
  name,
  ...rest
}: { name: string } & Omit<TextProps, 'children' | 'numberOfLines' | 'onTextLayout'>) {
  const needsAbbreviation = useMemo(() => shouldAbbreviatePlayerName(name), [name]);
  const [clipped, setClipped] = useState(false);
  const abbreviated = needsAbbreviation || clipped;
  return (
    <AppText
      {...rest}
      numberOfLines={1}
      onTextLayout={(event) => {
        // Already abbreviating (via the length threshold or an earlier
        // secondary detection) — nothing left to detect.
        if (abbreviated) return;
        // Can't check `lines.length > 1` here — with numberOfLines={1} also
        // set, RN caps the reported lines at 1 no matter what, so that check
        // can never fire. A truncated line's reported text is always
        // shorter than the real name (RN appends an ellipsis and drops what
        // didn't fit), so compare lengths instead.
        const renderedText = event.nativeEvent.lines[0]?.text ?? '';
        if (renderedText.length > 0 && renderedText.length < name.trim().length) {
          setClipped(true);
        }
      }}
    >
      {abbreviated ? abbreviatePlayerName(name) : name}
    </AppText>
  );
}
