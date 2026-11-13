import React, { useId, useMemo } from 'react';
import Svg, { ClipPath, Defs, G, Path, Text as SvgText } from 'react-native-svg';

import { simCrestArt, simCrestLabel, simCrestSpec } from '../lib/simCrest';

/**
 * A team's generated emblem (shape + pattern + colors + letter, all derived
 * from the team name; lib/simCrest.ts). Original artwork, the same crest on
 * every surface. Mirrors web-next's SimCrest.
 */
export default function SimCrest({ name, size = 28, label = false }: { name: string; size?: number; label?: boolean }) {
  const rawId = useId();
  const clipId = `crest${rawId.replace(/[^A-Za-z0-9]/g, '')}`;
  const spec = useMemo(() => simCrestSpec(name), [name]);
  const art = useMemo(() => simCrestArt(spec), [spec]);
  return (
    <Svg
      width={size}
      height={size}
      viewBox={art.viewBox}
      accessible={label}
      accessibilityLabel={label ? simCrestLabel(name) : undefined}
      importantForAccessibility={label ? 'yes' : 'no-hide-descendants'}
      testID="sim-crest"
    >
      <Defs>
        <ClipPath id={clipId}>
          <Path d={art.outline} />
        </ClipPath>
      </Defs>
      <Path d={art.outline} fill={spec.primary} />
      {art.pattern ? (
        <G clipPath={`url(#${clipId})`}>
          <Path d={art.pattern} fill={spec.secondary} opacity={0.92} />
        </G>
      ) : null}
      <Path d={art.outline} fill="none" stroke={spec.secondary} strokeWidth={3} strokeLinejoin="round" />
      <SvgText x={art.letterX} y={art.letterY} textAnchor="middle" fontSize={art.letterSize} fontWeight="900" fill="none" stroke={spec.halo} strokeWidth={4} strokeLinejoin="round" opacity={0.85}>
        {art.letter}
      </SvgText>
      <SvgText x={art.letterX} y={art.letterY} textAnchor="middle" fontSize={art.letterSize} fontWeight="900" fill={spec.ink}>
        {art.letter}
      </SvgText>
    </Svg>
  );
}
