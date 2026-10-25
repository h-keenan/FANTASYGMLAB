import React, { useMemo } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Line, Polygon, Text as SvgText } from 'react-native-svg';

import { useThemeMode } from '../context/ThemeModeContext';
import { radarPoints } from '../lib/playerQuickViewPresentation';
import type { SubRating } from '../lib/subRatings';

const SIZE = 220;
const CENTER = SIZE / 2;
const RADIUS = 76;
const RINGS = [0.33, 0.66, 1];

function pointAt(index: number, count: number, fraction: number): { x: number; y: number } {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
  return { x: CENTER + Math.cos(angle) * RADIUS * fraction, y: CENTER + Math.sin(angle) * RADIUS * fraction };
}

/**
 * Market/Opportunity/Scarcity/Role/Durability as a 5-axis radar: the same
 * real 0-99 values SubRatingRow shows as chips, drawn as a shape (web twin:
 * ModelRadarChart.tsx). Renders nothing unless every axis has a rating; the
 * caller falls back to the chip row (a missing axis plotted as 0 would read
 * as "worst", not "no read").
 */
export default function ModelRadarChart({ ratings }: { ratings: SubRating[] }) {
  const { colors } = useThemeMode();
  const points = useMemo(() => radarPoints(ratings), [ratings]);
  if (!points) return null;
  const count = points.length;
  const polygon = points
    .map((point, index) => {
      const p = pointAt(index, count, point.value / 99);
      return `${p.x},${p.y}`;
    })
    .join(' ');
  return (
    <View
      style={{ alignItems: 'center' }}
      accessible
      accessibilityLabel={`Model attributes: ${points.map((p) => `${p.label} ${p.value}`).join(', ')}`}
    >
      <Svg width={SIZE} height={SIZE}>
        {RINGS.map((fraction) => (
          <Polygon
            key={fraction}
            points={points.map((_, index) => {
              const p = pointAt(index, count, fraction);
              return `${p.x},${p.y}`;
            }).join(' ')}
            fill="none"
            stroke={colors.border}
            strokeWidth={1}
          />
        ))}
        {points.map((_, index) => {
          const p = pointAt(index, count, 1);
          return <Line key={`axis-${index}`} x1={CENTER} y1={CENTER} x2={p.x} y2={p.y} stroke={colors.border} strokeWidth={1} />;
        })}
        <Polygon points={polygon} fill={colors.accent} fillOpacity={0.28} stroke={colors.accent} strokeWidth={1.5} />
        {points.map((point, index) => {
          const p = pointAt(index, count, point.value / 99);
          return <Circle key={`dot-${point.label}`} cx={p.x} cy={p.y} r={2.5} fill={colors.accent} />;
        })}
        {points.map((point, index) => {
          const p = pointAt(index, count, 1.28);
          return (
            <SvgText
              key={`label-${point.label}`}
              x={p.x}
              y={p.y + 3}
              fontSize={10}
              fontWeight="700"
              fill={colors.textTertiary}
              textAnchor="middle"
            >
              {point.label}
            </SvgText>
          );
        })}
      </Svg>
    </View>
  );
}
