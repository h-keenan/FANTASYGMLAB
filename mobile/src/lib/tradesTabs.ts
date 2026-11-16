/**
 * The Trades host screen's tab labels. One name per workflow across surfaces:
 * the web TradesTabBar pills (Ideas / Finder / Grade a trade / History), the GM orb
 * search labels in lib/orbTabs.ts ("Trade Hub > Finder") and the feature
 * catalog all use these, and tradesTabs.test.ts pins app and orb together.
 * (History is its own screen here, reached from the header button.)
 *
 * Pure data, no react-native imports, so it runs under node:test.
 */
import { pageTabFamily } from './pageFamilies.ts';
import type { TabIconName } from './tabIcons';

export type TradesTab = 'block' | 'search' | 'make';

/** `key` is the TradesScreen route param (`initialTab`) the orb tabs also use. */
/** The label comes from the shared family data (lib/pageFamilies.ts), so the Trades strip and the web pill can never differ. */
function familyLabel(tabKey: string): string {
  return pageTabFamily('trades').tabs.find((t) => t.key === tabKey)?.label ?? tabKey;
}

export const TRADES_TAB_OPTIONS: Array<{ key: TradesTab; label: string; glyph: TabIconName; /** Paid tab: wears the Pro marker for anyone not on Pro. */ pro?: boolean }> = [
  { key: 'block', label: familyLabel('trade_hub'), glyph: 'hub' },
  { key: 'search', label: familyLabel('trade_finder'), glyph: 'finder', pro: true },
  { key: 'make', label: familyLabel('trade_analyzer'), glyph: 'analyzer' },
];
