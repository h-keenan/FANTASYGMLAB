import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

type IconName = React.ComponentProps<typeof Ionicons>['name'];

/** Icon-in-soft-colored-circle — the FGL design-reference-sheet treatment
 * for menu-like / action rows and story landmarks: a translucent disc of
 * the icon's own color (~15% alpha) behind the glyph, so a list of rows
 * scans by color before it scans by label. One implementation so GM Orb's
 * destination sheet, Home's quick actions, Recap stories, the recap-ready
 * banners, and More's menu rows all render the same disc. `color` must be
 * a 6-digit hex (the alpha is appended as a hex suffix). */
export default function IconCircle({
  name,
  color,
  size = 32,
  iconSize,
  style,
}: {
  name: IconName;
  color: string;
  /** Disc diameter; the icon defaults to half of it. */
  size?: number;
  iconSize?: number;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View
      style={[
        styles.circle,
        { width: size, height: size, borderRadius: size / 2, backgroundColor: `${color}26` },
        style,
      ]}
    >
      <Ionicons name={name} size={iconSize ?? Math.round(size / 2)} color={color} />
    </View>
  );
}

const styles = StyleSheet.create({
  circle: { alignItems: 'center', justifyContent: 'center' },
});
