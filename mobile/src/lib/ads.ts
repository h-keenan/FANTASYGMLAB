// AdMob (react-native-google-mobile-ads) is temporarily disabled — the
// package's current release pins a Google Ads SDK version that requires a
// newer Kotlin than Expo SDK 54 allows, breaking every Android build. This
// shim keeps the same exported surface (initAds/showRewardedAd) so callers
// (App.tsx, TradeHubScreen.tsx) need no changes: initAds() resolves
// immediately, showRewardedAd() always resolves false (the same "declined/
// unavailable" outcome the real implementation already returned when no ad
// unit was configured), and `adsAvailable` lets a screen hide ad-gated UI
// entirely instead of offering a button that can never succeed.
//
// To re-enable: restore the real implementation (see git history prior to
// this commit), re-add react-native-google-mobile-ads to package.json and
// the plugins list in app.json, and confirm it builds on Android first.

export const adsAvailable = false;

/** Call once at app startup — safe to call more than once. No-op while ads are disabled. */
export function initAds(): Promise<void> {
  return Promise.resolve();
}

/**
 * Show a rewarded ad and resolve `true` only once the viewer actually earned
 * the reward. Always resolves `false` while ads are disabled.
 */
export function showRewardedAd(): Promise<boolean> {
  return Promise.resolve(false);
}
