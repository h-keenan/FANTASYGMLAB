import { Platform } from 'react-native';
import mobileAds, { RewardedAd, RewardedAdEventType, AdEventType } from 'react-native-google-mobile-ads';

import { env } from './env';

const REWARDED_UNIT_ID = Platform.select({
  ios: env.admobIosRewardedUnitId,
  android: env.admobAndroidRewardedUnitId,
  default: env.admobAndroidRewardedUnitId,
});

let initPromise: Promise<void> | null = null;

/** Call once at app startup — safe to call more than once. */
export function initAds(): Promise<void> {
  if (!initPromise) {
    initPromise = mobileAds()
      .initialize()
      .then(() => undefined)
      .catch(() => undefined);
  }
  return initPromise;
}

/**
 * Show a rewarded ad and resolve `true` only once the viewer actually earned
 * the reward (watched it through) — resolves `false` on skip, close, load
 * failure, or a platform with no unit configured. Never throws.
 */
export function showRewardedAd(): Promise<boolean> {
  return new Promise((resolve) => {
    if (!REWARDED_UNIT_ID) {
      resolve(false);
      return;
    }
    const rewarded = RewardedAd.createForAdRequest(REWARDED_UNIT_ID);
    let earned = false;
    let settled = false;
    const finish = (result: boolean) => {
      if (settled) return;
      settled = true;
      unsubscribeLoaded();
      unsubscribeEarned();
      unsubscribeClosed();
      unsubscribeError();
      resolve(result);
    };
    const unsubscribeLoaded = rewarded.addAdEventListener(RewardedAdEventType.LOADED, () => {
      rewarded.show();
    });
    const unsubscribeEarned = rewarded.addAdEventListener(RewardedAdEventType.EARNED_REWARD, () => {
      earned = true;
    });
    const unsubscribeClosed = rewarded.addAdEventListener(AdEventType.CLOSED, () => {
      finish(earned);
    });
    const unsubscribeError = rewarded.addAdEventListener(AdEventType.ERROR, () => {
      finish(false);
    });
    rewarded.load();
  });
}
