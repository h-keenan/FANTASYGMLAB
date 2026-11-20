/**
 * Push-token handoff on sign-out (docs/audits/2026-11-push-token-handoff.md).
 *
 * The device's push token must leave the signed-out account on the server while the session can still
 * authorise the call, so that account's notifications never reach whoever signs in next. Order is fixed:
 * unregister first (best effort, short timeout, never throws), then drop the session. A different user
 * signing in re-registers the same token, and the backend moves it to them (one owner per token).
 *
 * Kill switch: PUSH_TOKEN_HANDOFF_ENABLED. `false` restores the previous behaviour (unregister awaited
 * with no timeout, only the token registered in this process).
 */
export const PUSH_TOKEN_HANDOFF_ENABLED = true;

export const PUSH_UNREGISTER_TIMEOUT_MS = 2500;

/** Resolves when `work` settles or after `ms`, whichever is first. Never rejects. */
export async function settleWithin(work: () => Promise<unknown>, ms: number): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<void>((resolve) => {
    timer = setTimeout(resolve, ms);
  });
  try {
    await Promise.race([Promise.resolve().then(work).catch(() => undefined), timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/** Unregister the push token, then drop the session. Sign-out is never blocked longer than the timeout. */
export async function unregisterThenDropSession(
  steps: { unregisterPush: () => Promise<void>; dropSession: () => Promise<void> },
  opts: { enabled?: boolean; timeoutMs?: number } = {},
): Promise<void> {
  const enabled = opts.enabled ?? PUSH_TOKEN_HANDOFF_ENABLED;
  if (enabled) {
    await settleWithin(steps.unregisterPush, opts.timeoutMs ?? PUSH_UNREGISTER_TIMEOUT_MS);
  } else {
    await steps.unregisterPush();
  }
  await steps.dropSession();
}
