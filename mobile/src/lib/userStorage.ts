import AsyncStorage from '@react-native-async-storage/async-storage';

import { resetAccountCaches } from './accountCaches';
import type { AsyncKeyValueStore } from './accountScope';
import { createUserStorage } from './userStorageCore';

/** The app's single user-scoped store (AsyncStorage). Use `userStorage.get/set/remove` for any per-user local state. */
export const userStorage = createUserStorage(AsyncStorage as unknown as AsyncKeyValueStore);

/** The one app purge: all user-scoped and unscoped account keys. React Query's cache is cleared by clearAuthenticatedQueryCache. */
export function purgeAccountStorage(): Promise<void> {
  resetAccountCaches();
  return userStorage.purge();
}
