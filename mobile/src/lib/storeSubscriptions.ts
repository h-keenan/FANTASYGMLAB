import { Linking, Platform } from 'react-native';

/**
 * Opens the platform's own subscription settings. Apple and Google require
 * cancel/change to go through the store, not a custom in-app flow. Shared by
 * More's "Manage Subscription" row and the GM orb's Premium row for store
 * subscribers.
 */
export function openStoreSubscriptionSettings(): void {
  const url =
    Platform.OS === 'ios'
      ? 'https://apps.apple.com/account/subscriptions'
      : 'https://play.google.com/store/account/subscriptions';
  void Linking.openURL(url);
}
