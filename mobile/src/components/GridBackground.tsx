import React from 'react';
import { StyleSheet } from 'react-native';
import Svg, { Defs, Path, Pattern, Rect } from 'react-native-svg';

import { colors } from '../theme';

const CELL = 72;

/**
 * The web app's ops-grid texture (modules/interface_reimagining_styles.py's
 * `.stApp` rule): a 72x72 logical-px line grid over the background, present
 * on every screen there. Ported as the same technique (tile size, hairline
 * width) rather than eyeballed — this is the single most identifiable "does
 * it feel like the same app" signal the web app has that mobile was
 * missing entirely.
 */
export default function GridBackground() {
  return (
    <Svg pointerEvents="none" style={StyleSheet.absoluteFillObject}>
      <Defs>
        <Pattern id="opsGrid" width={CELL} height={CELL} patternUnits="userSpaceOnUse">
          <Path d={`M ${CELL} 0 L 0 0 0 ${CELL}`} fill="none" stroke={colors.hairline} strokeWidth={1} />
        </Pattern>
      </Defs>
      <Rect x={0} y={0} width="100%" height="100%" fill="url(#opsGrid)" />
    </Svg>
  );
}
