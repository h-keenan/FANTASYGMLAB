/**
 * The Trades host screen's tab labels. One name per workflow across surfaces:
 * the web TradesTabBar pills (Hub / Finder / Analyzer / History), the GM orb
 * search labels in lib/orbTabs.ts ("Trade Hub > Finder") and the feature
 * catalog all use these, and tradesTabs.test.ts pins app and orb together.
 * (History is its own screen here, reached from the header button.)
 *
 * Pure data, no react-native imports, so it runs under node:test.
 */
export type TradesTab = 'block' | 'search' | 'make';

/** `key` is the TradesScreen route param (`initialTab`) the orb tabs also use. */
export const TRADES_TAB_OPTIONS: Array<{ key: TradesTab; label: string }> = [
  { key: 'block', label: 'Hub' },
  { key: 'search', label: 'Finder' },
  { key: 'make', label: 'Analyzer' },
];
