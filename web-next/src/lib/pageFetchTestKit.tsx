import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";

import { ValuationLensProvider } from "@/context/ValuationLensContext";
import { api } from "@/lib/api";

/**
 * Shared helpers for the per-page "requests start concurrently" tests.
 * Test-only; nothing in the app imports this file.
 */

export interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
}

export function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** Sleeper's settings.type: 0 redraft, 1 keeper, 2 dynasty. */
export function mockLeagueType(type: number) {
  vi.mocked(api.getLeague).mockResolvedValue({ league: { settings: { type } } } as never);
}

export function renderWithLens(ui: ReactElement) {
  return render(<ValuationLensProvider>{ui}</ValuationLensProvider>);
}

export const signedIn = {
  session: { user: { id: "user-1" } } as never,
  loading: false,
  signIn: vi.fn(),
  signUp: vi.fn(),
  signInWithOAuth: vi.fn(),
  signInAsGuest: vi.fn(),
  signOut: vi.fn(),
  deleteAccount: vi.fn(),
  upgradeGuestWithEmail: vi.fn(),
  callbackNotice: null,
  isGuest: false,
};
