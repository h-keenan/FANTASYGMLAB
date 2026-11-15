import React from 'react';
import { Image, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { leagueCrestColors, leagueInitials } from '../lib/leagueCrest';

/**
 * The league's picture: its avatar when a caller has one, else the generated crest (a stable colour per league id with the league's
 * initials, lib/leagueCrest.ts). Twin of web-next's components/LeagueCrest.tsx.
 */
export default function LeagueCrest({ leagueId, name, avatarUrl, size = 32 }: { leagueId?: string | null; name?: string | null; avatarUrl?: string | null; size?: number }) {
  const dim = { width: size, height: size, borderRadius: size / 2 };
  if (avatarUrl) return <Image source={{ uri: avatarUrl }} style={dim} accessibilityIgnoresInvertColors />;
  const c = leagueCrestColors(leagueId || name);
  return (
    <View style={[styles.base, dim, { backgroundColor: c.fill, borderColor: c.ring }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants" testID="league-crest">
      <AppText style={{ color: c.ink, fontWeight: '800', fontSize: Math.max(10, Math.round(size * 0.36)) }}>{leagueInitials(name)}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({ base: { alignItems: 'center', justifyContent: 'center', borderWidth: 2 } });
