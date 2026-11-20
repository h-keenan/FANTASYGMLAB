/**
 * Persistence for the college-football interest answer, per user (docs/audits/2026-11-account-isolation.md).
 * Personal preference, so it lives under the signed-in user's scope; the first sign-in after the upgrade adopts the
 * old plain keys (LEGACY_SCOPED_BASES), and the purge keeps it (USER_SCOPED_KEEP_BASES). Storage-agnostic for tests.
 */
import type { UserStorage } from './userStorageCore.ts';

export const COLLEGE_ANSWERED_KEY = 'fgl:college-football-prompt-answered';
export const COLLEGE_FOLLOWS_KEY = 'fgl:college-football-interest';

export type CollegeInterestAnswer = 'unanswered' | 'yes' | 'no';

type Store = Pick<UserStorage, 'get' | 'set'>;

export async function loadCollegeInterest(store: Store): Promise<CollegeInterestAnswer> {
  const [answered, follows] = await Promise.all([store.get(COLLEGE_ANSWERED_KEY), store.get(COLLEGE_FOLLOWS_KEY)]);
  if (answered !== '1') return 'unanswered';
  return follows === 'yes' ? 'yes' : 'no';
}

/** `follows` null = dismissed without answering (never ask again, entry point stays hidden). */
export async function saveCollegeInterest(store: Store, follows: boolean | null): Promise<void> {
  await store.set(COLLEGE_ANSWERED_KEY, '1');
  if (follows !== null) await store.set(COLLEGE_FOLLOWS_KEY, follows ? 'yes' : 'no');
}
