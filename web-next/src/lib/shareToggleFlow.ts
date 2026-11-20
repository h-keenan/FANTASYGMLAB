/**
 * Share-to-community toggle flow, one definition for web and app (byte-identical lib twin, imports nothing).
 * Audit: docs/audits/2026-11-client-data-races.md (follow-up) and 2026-11-account-isolation.md.
 *
 * Turning the switch off must win. A share request that is still in flight when the user switches off cannot be undone
 * by id yet, so the off request waits for the share to settle and then removes the trade it created. Actions are
 * serialized: a second share while one is pending is dropped, and an off request issued during a share is remembered
 * and applied as soon as the id is known.
 */

/** Kill switch. `false` restores the previous behaviour (off only removes a trade whose id is already known). */
export const SHARE_OFF_WINS_ENABLED = true;

export interface ShareToggleFlowOptions {
  /** Removes a shared trade; resolves true when it is gone. Rejection or false means it is still public. */
  unshare: (id: string) => Promise<boolean>;
  enabled?: boolean;
}

/** Sends the share; resolves with the new trade id, or null when sharing is unavailable. */
export type ShareFn = () => Promise<string | null>;
export type ShareOutcome = "shared" | "unavailable" | "error" | "dropped" | "cancelled" | "stuck-public";
export type OffOutcome = "off" | "still-public" | "nothing";

export interface ShareToggleFlow {
  /** "cancelled" means off won and the just-created trade was removed; "stuck-public" means that removal failed. */
  requestShare(share: ShareFn): Promise<ShareOutcome>;
  /** "still-public" means the delete failed and the id is kept so the user can retry. */
  requestOff(): Promise<OffOutcome>;
  readonly sharedId: string | null;
  readonly sharing: boolean;
}

export function createShareToggleFlow(opts: ShareToggleFlowOptions): ShareToggleFlow {
  const enabled = opts.enabled ?? SHARE_OFF_WINS_ENABLED;
  let sharedId: string | null = null;
  let inFlight: Promise<unknown> | null = null;
  let offWanted = false;

  async function removeId(id: string): Promise<boolean> {
    try {
      return (await opts.unshare(id)) !== false;
    } catch {
      return false;
    }
  }

  return {
    get sharedId() {
      return sharedId;
    },
    get sharing() {
      return inFlight !== null;
    },
    async requestShare(share) {
      if (inFlight) return "dropped";
      offWanted = false;
      let outcome: ShareOutcome = "error";
      const run = (async () => {
        let id: string | null = null;
        try {
          id = await share();
        } catch {
          outcome = "error";
          return;
        }
        if (!id) {
          outcome = "unavailable";
          return;
        }
        if (enabled && offWanted) {
          // The user switched off while this was in flight: off wins, remove what was just created.
          if (await removeId(id)) outcome = "cancelled";
          else {
            sharedId = id;
            outcome = "stuck-public";
          }
          return;
        }
        sharedId = id;
        outcome = "shared";
      })();
      inFlight = run;
      await run;
      inFlight = null;
      return outcome;
    },
    async requestOff() {
      if (enabled && inFlight) {
        offWanted = true;
        await inFlight.catch(() => undefined);
      }
      const id = sharedId;
      if (!id) return "nothing";
      sharedId = null;
      if (await removeId(id)) return "off";
      sharedId = id;
      return "still-public";
    },
  };
}
