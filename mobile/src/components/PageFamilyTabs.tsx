import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';

import SegmentedTabBar from './SegmentedTabBar';
import { pageTabFamily, activePageTab, type PageTabFamilyKey } from '../lib/pageFamilies';
import { familyRoute, familyTabOptions } from '../lib/pageFamilyRoutes';
import { spacing } from '../theme';

/**
 * The app's twin of web's PageTabBar: the ONE tab row of a page family (Trades / Team / League), the same tabs, labels
 * and glyphs from lib/pageFamilies.ts. A screen renders it at the top; picking a sibling opens that screen in place
 * (`replace`, so the back stack does not grow one entry per tab), except tabs the host handles itself (`onLocalSelect`
 * returns true), e.g. the Trades host's Hub / Finder / Analyzer panes.
 */
export default function PageFamilyTabs({
  family,
  active,
  leagueId,
  leagueName,
  onLocalSelect,
  padded = true,
}: {
  family: PageTabFamilyKey;
  /** A tab key from lib/pageFamilies.ts (e.g. "waivers", "trade_finder"). */
  active: string;
  leagueId: string;
  leagueName: string;
  onLocalSelect?: (key: string) => boolean;
  /** Horizontal gutter for screens whose content is not already padded. */
  padded?: boolean;
}) {
  const navigation = useNavigation<any>();
  const def = pageTabFamily(family);
  const options = useMemo(() => familyTabOptions(family, leagueId), [family, leagueId]);
  if (options.length < 2) return null;
  return (
    <View style={padded ? styles.wrap : styles.inline} accessibilityLabel={def.label}>
      <SegmentedTabBar<string>
        options={options}
        active={activePageTab(def, active)}
        scrollable
        onChange={(key) => {
          if (key === active) return;
          if (onLocalSelect?.(key)) return;
          const tab = def.tabs.find((t) => t.key === key);
          if (!tab) return;
          const route = familyRoute(tab, leagueId, leagueName);
          navigation.replace(route.name, route.params);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  inline: { paddingBottom: spacing.sm },
  wrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.sm },
});
