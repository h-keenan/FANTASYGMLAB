import React from 'react';
import Svg, { Path } from 'react-native-svg';

/** The trophy mark (championship / playoff recap pages). Twin of web-next/src/components/TrophyIcon.tsx. Decorative unless `label` is given. */
export default function TrophyIcon({ size = 72, color, label }: { size?: number; color: string; label?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" fill="none" accessible={Boolean(label)} accessibilityLabel={label} accessibilityRole={label ? 'image' : undefined} testID="trophy-icon">
      <Path d="M20 8h24v14a12 12 0 0 1-24 0V8Z" fill={color} fillOpacity={0.9} />
      <Path d="M20 12H10v4a10 10 0 0 0 10.6 10M44 12h10v4a10 10 0 0 1-10.6 10" stroke={color} strokeWidth={3} strokeLinecap="round" />
      <Path d="M32 34v10M24 56h16M26 44h12l2 12H24l2-12Z" stroke={color} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
      <Path d="M26 14v8" stroke="#ffffff" strokeOpacity={0.45} strokeWidth={3} strokeLinecap="round" />
    </Svg>
  );
}
