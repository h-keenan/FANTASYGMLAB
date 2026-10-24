import React, { useEffect, useMemo } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Defs, LinearGradient as SvgLinearGradient, Path, RadialGradient, Rect, Stop } from 'react-native-svg';

import { useThemeMode } from '../context/ThemeModeContext';
import { gradients, lightGradients } from '../theme';

/**
 * The app's single ambient page background, mounted ONCE at the navigation
 * root (RootNavigator) behind every screen: the native port of web-next's
 * `.app-background-field` + `.app-background-sweep` (globals.css), which
 * paint the same drifting diagonal field lines and a slow light sweep
 * behind every web page.
 *
 * Layers, back to front: the navy/ice wash + accent bloom (previously
 * painted per screen by GridBackground), the field lines, the sweep.
 *
 * Cost: the line pattern is a static SVG drawn once; only two native-thread
 * transforms are animated (field translateX, sweep translateX), so there is
 * no JS work per frame. Fully static when the OS asks for reduced motion.
 * Line/sweep colors mirror web: white in dark mode, dark ink in light mode.
 */

// CSS: repeating-linear-gradient(112deg, ... 3px line every 96px, 1.5px every 24px).
const ANGLE = (112 * Math.PI) / 180;
const SIN = Math.sin(ANGLE);
const SHEAR = Math.abs(Math.cos(ANGLE)) / SIN; // horizontal run per px of height
const MAJOR_PERIOD = 96 / SIN; // horizontal distance between major lines
const MINOR_PERIOD = 24 / SIN; // divides MAJOR_PERIOD exactly (x4), so one loop is seamless

// Web shifts the field 480px per 14s (~34px/s); one horizontal period per
// loop keeps that speed.
const DRIFT_PERIOD_MS = Math.round((MAJOR_PERIOD / 480) * 14000);
const SWEEP_MS = 9000; // web: 9s ease-in-out infinite

function linePath(periodPx: number, width: number, height: number): string {
  const shear = SHEAR * height;
  let d = '';
  for (let x = -shear - periodPx; x <= width + periodPx * 2; x += periodPx) {
    d += `M${x.toFixed(1)} ${height} L${(x + shear).toFixed(1)} 0 `;
  }
  return d;
}

export default function AppBackground() {
  const { colors, isDark } = useThemeMode();
  const { width, height } = useWindowDimensions();
  const reduceMotion = useReducedMotion();

  const drift = useSharedValue(0);
  const sweep = useSharedValue(0);

  useEffect(() => {
    if (reduceMotion) {
      cancelAnimation(drift);
      cancelAnimation(sweep);
      drift.value = 0;
      sweep.value = 0.35;
      return;
    }
    drift.value = 0;
    drift.value = withRepeat(withTiming(1, { duration: DRIFT_PERIOD_MS, easing: Easing.linear }), -1, false);
    sweep.value = 0;
    sweep.value = withRepeat(withTiming(1, { duration: SWEEP_MS, easing: Easing.inOut(Easing.ease) }), -1, false);
    return () => {
      cancelAnimation(drift);
      cancelAnimation(sweep);
    };
  }, [reduceMotion, drift, sweep]);

  const sweepWidth = width * 0.34;
  const fieldStyle = useAnimatedStyle(() => ({ transform: [{ translateX: drift.value * MAJOR_PERIOD }] }));
  const sweepStyle = useAnimatedStyle(() => ({
    // web: translateX(-60%) -> translateX(160%) of its own width, rotated 18deg.
    transform: [{ translateX: (-0.6 + 2.2 * sweep.value) * sweepWidth }, { rotate: '18deg' }],
  }));

  const wash = isDark ? gradients.hero : lightGradients.headerWash;
  const ink = isDark ? '255,255,255' : '16,24,32';
  const majorOpacity = isDark ? 0.1 : 0.07;
  const minorOpacity = isDark ? 0.035 : 0.025;
  const fieldOpacity = isDark ? 0.4 : 0.5;
  const peak = isDark ? 0.1 : 0.08;
  const edge = isDark ? 0.05 : 0.04;

  const majorD = useMemo(() => linePath(MAJOR_PERIOD, width, height), [width, height]);
  const minorD = useMemo(() => linePath(MINOR_PERIOD, width, height), [width, height]);

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <Svg style={StyleSheet.absoluteFill}>
        <Defs>
          <SvgLinearGradient id="appWash" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={wash[0]} stopOpacity={1} />
            <Stop offset="1" stopColor={wash[1]} stopOpacity={1} />
          </SvgLinearGradient>
          <RadialGradient id="appBloom" cx="0.5" cy="0" r="0.65">
            <Stop offset="0" stopColor={colors.accent} stopOpacity={isDark ? 0.12 : 0.1} />
            <Stop offset="1" stopColor={colors.accent} stopOpacity={0} />
          </RadialGradient>
        </Defs>
        <Rect x={0} y={0} width="100%" height="100%" fill="url(#appWash)" />
        <Rect x={0} y={0} width="100%" height="100%" fill="url(#appBloom)" />
      </Svg>

      <Animated.View style={[StyleSheet.absoluteFill, { opacity: fieldOpacity }, fieldStyle]} renderToHardwareTextureAndroid>
        <Svg width={width + MAJOR_PERIOD} height={height}>
          <Path d={minorD} stroke={`rgba(${ink},${minorOpacity})`} strokeWidth={1.5} />
          <Path d={majorD} stroke={`rgba(${ink},${majorOpacity})`} strokeWidth={3} />
        </Svg>
      </Animated.View>

      <Animated.View
        style={[{ position: 'absolute', top: -0.2 * height, left: 0, width: sweepWidth, height: height * 1.4 }, sweepStyle]}
        renderToHardwareTextureAndroid
      >
        <LinearGradient
          style={StyleSheet.absoluteFill}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          colors={[
            `rgba(${ink},0)`,
            `rgba(${ink},${edge})`,
            `rgba(${ink},${peak})`,
            `rgba(${ink},${edge})`,
            `rgba(${ink},0)`,
          ]}
          locations={[0, 0.45, 0.5, 0.55, 1]}
        />
      </Animated.View>
    </View>
  );
}
